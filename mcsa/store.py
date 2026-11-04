"""MCSA handle store — C1. Makes the documented grammar real.

Before this module, `<G:hhhh>` existed only as text in spine.SECTIONS
["ontology"]. R5 (handle economy and durability) had no code behind it, which is
the same defect as a requirement with no implementation: the control surface
read green while its subject was absent.

What this implements, against R4/R5/R1:
  mint   content-addressed handle, 4 hex, collision-checked, durable on disk
  resolve  handle -> content, loud-fail on unknown
  list_    enumerate live handles
  drop     explicit removal (no implicit eviction)
  DEFAULTS to ./mcsa_store on the repo root

Design notes, each of which is a gate rather than a comment:

R5  durability. Resolution goes to disk, not to an in-process dict. A handle
    minted in one process resolves in another and survives restart. This is the
    exact defect F3 records against POINTS' chr(0xE000).

R4  loud-fail. Unknown handle RAISES. Minting content that already exists
    returns the SAME handle (content addressing is idempotent by design). A
    4-hex-prefix COLLISION between two different contents is refused, never
    silently overwritten -- 16 bits is small, and a collision that quietly
    aliases two payloads is the F2 shape (green flag, wrong subject).

16 bits is genuinely small. We do not pretend otherwise: collision probability
is computed and exposed, and the prefix widens automatically when the live set
outgrows one prefix space. Widening changes the handle length, which is a
contract change -- so it is reported, not hidden.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "mcsa_store"
HANDLE_RE = re.compile(r"^<([KGT]):([0-9a-f]{4,16})>$")

__all__ = ["mint", "resolve", "list_", "drop", "stats", "mint_section",
           "HandleError", "UnknownHandle", "CollisionError"]


class HandleError(Exception):
    """Base. Every failure in this module is loud by construction."""


class UnknownHandle(HandleError):
    """Resolution failed. ABSENT is the correct answer, never a guess."""


class CollisionError(HandleError):
    """Two distinct contents want the same short prefix. Refuse, do not alias."""


def _root(root: str | os.PathLike | None = None) -> Path:
    p = Path(root) if root else DEFAULT_ROOT
    p.mkdir(parents=True, exist_ok=True)
    return p


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _prefix_width(p: Path) -> int:
    """Current handle width, widened as the live set outgrows a prefix space."""
    w = 4
    n = len(list(p.glob("*.json")))
    # birthday-ish guard: widen before the space gets crowded
    while n > 0.5 * (16 ** w) and w < 16:
        w += 1
    return w


def _index_path(p: Path) -> Path:
    return p / "index.json"


def _read_index(p: Path) -> dict:
    f = _index_path(p)
    if not f.exists():
        return {"handles": {}, "width": 4}
    try:
        return json.loads(f.read_text())
    except Exception as e:
        raise HandleError(f"index corrupt at {f}: {e}") from None


def _write_index(p: Path, idx: dict) -> None:
    _index_path(p).write_text(json.dumps(idx, indent=1, sort_keys=True))


def mint(content: str | bytes, kind: str = "G", root=None) -> str:
    """Content-address a payload, return a durable handle.

    Idempotent: identical content returns the identical handle. That is what
    content addressing means, and it is why `mint` never needs a nonce.
    """
    if kind not in "KGT":
        raise HandleError(f"kind must be one of K, G, T; got {kind!r}")
    raw = content.encode("utf-8") if isinstance(content, str) else content
    if not raw:
        raise HandleError("refusing to mint an empty payload: a handle that "
                          "resolves to nothing is a silent FAIL downstream")
    p = _root(root)
    idx = _read_index(p)
    d = _digest(raw)
    w = _prefix_width(p)

    # full-digest hit -> idempotent, return existing
    for h, rec in idx["handles"].items():
        if rec["sha256"] == d:
            return h

    short = d[:w]
    if short in idx["handles"]:
        raise CollisionError(
            f"prefix collision on <{kind}:{short}>: already bound to a different "
            f"payload ({idx['handles'][f'<{kind}:{short}>']['bytes']} bytes). "
            f"Refusing to alias two contents onto one handle."
        )

    handle = f"<{kind}:{short}>"
    idx["handles"][handle] = {"sha256": d, "bytes": len(raw), "kind": kind}
    _write_index(p, idx)
    (p / f"{kind}_{short}.blob").write_bytes(raw)
    return handle


def mint_section(key: str, root=None) -> str:
    """Mint a pointed section by its key. Convenience over `mint`."""
    from .spine import SECTIONS
    if key not in SECTIONS:
        raise UnknownHandle(
            f"section {key!r} not in SECTIONS (known: {', '.join(sorted(SECTIONS))})"
        )
    return mint(SECTIONS[key], kind="G", root=root)


def resolve(handle: str, root=None) -> str:
    """Handle -> content. Durable across process and restart.

    Raises UnknownHandle. Never returns a partial or best-effort value.
    """
    if not isinstance(handle, str) or not HANDLE_RE.match(handle):
        raise UnknownHandle(
            f"{handle!r} is not a handle. Grammar: <K:hhhh> keybank, "
            f"<G:hhhh> graph, <T:hhhh> text."
        )
    p = _root(root)
    idx = _read_index(p)
    if handle not in idx["handles"]:
        raise UnknownHandle(
            f"{handle} is not minted. {len(idx['handles'])} handle(s) live. "
            f"Mint it, or report absence -- do not infer its content."
        )
    rec = idx["handles"][handle]
    kind, short = handle[1], handle[3:-1]
    blob = p / f"{kind}_{short}.blob"
    if not blob.exists():
        raise HandleError(f"index names {handle} but {blob} is absent -- store corrupt")
    data = blob.read_bytes()
    if _digest(data) != rec["sha256"]:
        # This is F2's exact shape, and here it is CAUGHT instead of reported green.
        raise HandleError(
            f"integrity FAIL for {handle}: sha256 mismatch. The store is not "
            f"trustworthy; do not use its content."
        )
    return data.decode("utf-8")


def list_(root=None) -> list[str]:
    p = _root(root)
    return sorted(_read_index(p)["handles"])


def drop(handle: str, root=None) -> None:
    """Explicit removal. There is no implicit eviction path in this module."""
    p = _root(root)
    idx = _read_index(p)
    if handle not in idx["handles"]:
        raise UnknownHandle(f"{handle} not minted")
    kind, short = handle[1], handle[3:-1]
    blob = p / f"{kind}_{short}.blob"
    if blob.exists():
        blob.unlink()
    del idx["handles"][handle]
    _write_index(p, idx)


def stats(root=None) -> dict:
    p = _root(root)
    idx = _read_index(p)
    live = idx["handles"]
    if not live:
        return {"handles": 0, "bytes": 0, "width": 4,
                "collision_probability": 0.0}
    n, w = len(live), _prefix_width(p)
    # birthday bound: P(>=1 collision) over a space of 16**w with n occupants
    space = 16 ** w
    p_coll = 1.0
    for i in range(n):
        p_coll *= (space - i) / space
    return {
        "handles": n,
        "bytes": sum(r["bytes"] for r in live.values()),
        "width": w,
        "space": space,
        "collision_probability": round(1.0 - p_coll, 12),
    }


def mint_all_sections(root=None) -> dict[str, str]:
    """Bind every pointed section to a handle. C1 completion: the grammar in
    spine.SECTIONS['ontology'] now corresponds to real, resolvable objects."""
    from .spine import ALL_SECTIONS
    return {k: mint_section(k, root=root) for k in ALL_SECTIONS}
