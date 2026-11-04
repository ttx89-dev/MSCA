"""MCSA capacity measurement — C2. Implements R3.

R3 said: capacity SHALL be computed by an executable check and recorded at deploy
time; no claim of capacity may appear without a measurement artifact and its
command. Until this module existed, R3 was a requirement with no implementation
behind it -- the same defect as C1, and the very shape of failure (a control
reading green while its subject is absent) that F4 documents.

    capacity = reachable_information / permanently_resident_tokens

"Reachable" is counted as bytes reachable by handle or by a named loader key.
"Resident" is measured with the WORST available real tokenizer (see tokens.py),
never with chars/4.

The record is written to mcsa_store/capacity.json and is expected to be
committed. A capacity claim with no record in the tree is not a claim.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from . import store, tokens
from .loader import ALL_SECTIONS, PHASES, TAGS, coverage
from .spine import RESIDENT

RECORD = Path(__file__).resolve().parent.parent / "mcsa_store" / "capacity.json"

# ── D5: the capacity floor ──────────────────────────────────────────────────
#
# R3 requires a measurement to exist. It did NOT require the measurement to be
# GOOD. A record that only proves "something was measured" lets an edit halve
# the reachable tier and pass every gate. D5 closes that.
#
# UNIT: bits of reachable content per permanently-resident token. Higher is
# better. Reference 1x = 166.9 with the whole pointed tier reachable.
#
# SET BELOW THE MEASUREMENT ON PURPOSE. A floor equal to the current value is a
# trap: an edit that both regresses and re-records lands exactly on the line and
# passes. 150 keeps ~10% headroom for tokenizer drift while still failing on
# real decay. Tightening past that trades noise-tolerance for detection latency,
# which is an owner call — change it here, visibly, and re-record.
#
# MECHANISM (laya noul 0.8025 that a raise-only explicit-edit floor is right):
# the floor is a constant with provenance, not a derived value. It cannot track
# the measurement, because a floor that tracks the measurement measures nothing.
FLOOR_ENV = "MCSA_CAPACITY_FLOOR"
CAPACITY_FLOOR = 150.0


def floor() -> float:
    import os
    raw = os.environ.get(FLOOR_ENV)
    if not raw:
        return CAPACITY_FLOOR
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"{FLOOR_ENV}={raw!r} is not a number; refusing to guess a floor. "
            f"Unset it to use the approved floor of {CAPACITY_FLOOR}."
        ) from None


def _commit(root: str | Path) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=root, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def measure(root: str | Path | None = None) -> dict:
    base = Path(root) if root else Path(__file__).resolve().parent.parent
    res = tokens.measure(RESIDENT)
    # Count the resident tier ONCE. An earlier version folded len(RESIDENT)
    # into the per-section sum, counting it once per section (7x) and inflating
    # capacity from 171.7 to 335.0 bits/token. The floor still passed under the
    # inflated number, which is the point: a wrong metric that clears the bar is
    # worse than a missing one.
    from .spine import SECTIONS
    reachable_bytes = len(RESIDENT) + sum(len(SECTIONS[k]) for k in ALL_SECTIONS)
    resident_tokens = res["governing"]
    cov = coverage()
    return {
        "schema": "mcsa.capacity/1",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "commit": _commit(base),
        "resident_tokens": resident_tokens,
        "resident_method": res["method"],
        "resident_worst_encoding": res["worst_encoding"],
        "resident_counts": res["counts"],
        "resident_chars": res["chars"],
        "ceiling": tokens.ceiling(),
        "reachable_bytes": reachable_bytes,
        "capacity_bits_per_resident_token": round(
            reachable_bytes * 8 / resident_tokens, 3) if resident_tokens else 0.0,
        "sections": len(ALL_SECTIONS),
        "phases": len(PHASES),
        "tags": len(TAGS),
        "capacity_floor": floor(),
        "capacity_floor_met": round(reachable_bytes * 8 / resident_tokens, 3)
        >= floor() if resident_tokens else False,
        "unreachable_sections": sorted(cov["unreachable"]),
        "handles_minted": len(store.list_(root=base)),
        "command": "python -m mcsa.capacity --record",
    }


def write(root: str | Path | None = None) -> dict:
    rec = measure(root)
    p = RECORD if root is None else Path(root) / "mcsa_store" / "capacity.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    rec["written_to"] = str(p)
    return rec


def floor_verdict(root=None) -> dict:
    """VALIDATABLE: is the live capacity at or above the approved floor?

    Separate from verify() on purpose. verify() asks "does the record match the
    code"; this asks "is the code still worth deploying". A tree can satisfy the
    first and fail the second -- that is precisely the decay D5 exists to catch.
    """
    live = measure(root)
    v = live["capacity_bits_per_resident_token"]
    f = floor()
    return {"value": v, "floor": f, "ok": v >= f,
            "headroom": round(v - f, 3),
            "verdict": "AT FLOOR" if v >= f else "BELOW FLOOR — deployment blocked"}


def verify(root: str | Path | None = None) -> dict:
    """VALIDATABLE: does the recorded claim match the code as it is NOW?

    A stale record is a false claim. Drift between the record and the source is
    a failure, not a cosmetic mismatch -- the record exists to be checkable.
    """
    p = RECORD if root is None else Path(root) / "mcsa_store" / "capacity.json"
    if not p.exists():
        return {"ok": False, "reason": "no record; run: python -m mcsa.capacity --record"}
    try:
        recorded = json.loads(p.read_text())
    except Exception as e:
        return {"ok": False, "reason": f"record unparseable: {e}"}
    live = measure(root)
    drift = []
    for k in ("resident_tokens", "reachable_bytes", "sections", "phases", "tags"):
        if recorded.get(k) != live.get(k):
            drift.append(f"{k}: record={recorded.get(k)} live={live.get(k)}")
    if recorded.get("unreachable_sections") != live.get("unreachable_sections"):
        drift.append("unreachable_sections differs")
    return {"ok": not drift, "drift": drift,
            "recorded_at": recorded.get("measured_at"),
            "recorded_commit": recorded.get("commit")}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mcsa.capacity")
    ap.add_argument("--record", action="store_true", help="measure and write the record")
    ap.add_argument("--verify", action="store_true", help="check record vs live code")
    ap.add_argument("--floor", action="store_true", help="check capacity against D5 floor")
    a = ap.parse_args()

    if a.floor:
        fv = floor_verdict()
        print(f"capacity {fv['value']} bits/resident-token  floor {fv['floor']}  "
              f"headroom {fv['headroom']:+}  {fv['verdict']}")
        return 0 if fv["ok"] else 1

    if a.verify:
        v = verify()
        print("capacity record:", "MATCHES code" if v["ok"] else "DRIFT")
        if not v["ok"]:
            print("  reason:", v.get("reason", ""))
            for d in v.get("drift", []):
                print("  drift :", d)
        print(f"  recorded_at={v.get('recorded_at')} commit={v.get('recorded_commit')}")
        return 0 if v["ok"] else 1

    rec = write() if a.record else measure()
    if a.record:
        rec.pop("written_to", None)
    print(json.dumps(rec, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
