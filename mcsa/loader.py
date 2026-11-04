"""MCSA loader — phase/tag-keyed selective subgraph retrieval.

SCRIPTABLE:  python -m mcsa.loader --phase 12
             python -m mcsa.loader --tag safety
             python -m mcsa.loader --phase 12 --tag safety
             python -m mcsa.loader --all
             python -m mcsa.loader --resident
             python -m mcsa.loader --list

Selectivity is the point: with prose you load "the safety section"; with this
index you load the union of sections reachable from the current phase and tag.
That is the capability a flat file cannot provide, and it is why the ontology
was applied to the prompt rather than merely compressing it.
"""

from __future__ import annotations

import argparse
import sys

from .spine import ALL_SECTIONS, PHASES, RESIDENT, SECTIONS, TAGS

__all__ = [
    "for_phase", "for_tag", "for_phase_and_tag", "everything",
    "resident", "list_keys", "coverage", "unknown_keys",
]


def _emit(keys: tuple[str, ...]) -> str:
    return "\n\n".join(SECTIONS[k] for k in keys)


def resident() -> str:
    """Tier 1. Pre-decision content. Inlined into the system prompt."""
    return RESIDENT


def for_phase(phase: int) -> str:
    """Subgraph bound to a refinement-loop phase (1-15)."""
    if phase not in PHASES:
        raise KeyError(
            f"phase {phase} not in index (known: {min(PHASES)}-{max(PHASES)}). "
            f"Unknown phase is a FAIL, not an empty result."
        )
    return _emit(PHASES[phase])


def for_tag(tag: str) -> str:
    """Subgraph bound to a semantic tag."""
    if tag not in TAGS:
        raise KeyError(
            f"tag {tag!r} not in index (known: {', '.join(sorted(TAGS))}). "
            f"Unknown tag is a FAIL, not an empty result."
        )
    return _emit(TAGS[tag])


def for_phase_and_tag(phase: int, tag: str) -> str:
    """Union, order-stable, de-duplicated. Both keys are optional individually
    but at least one must be present."""
    keys: list[str] = []
    for k in (*PHASES.get(phase, ()), *TAGS.get(tag, ())):
        if k not in keys:
            keys.append(k)
    if not keys:
        raise KeyError(f"phase {phase} + tag {tag!r} resolves to no sections")
    return _emit(tuple(keys))


def everything() -> str:
    return _emit(ALL_SECTIONS)


def list_keys() -> str:
    out = ["PHASES"]
    for p in sorted(PHASES):
        out.append(f"  {p:>2}  {', '.join(PHASES[p])}")
    out.append("TAGS")
    for t in sorted(TAGS):
        out.append(f"  {t:<8} {', '.join(TAGS[t])}")
    return "\n".join(out)


def coverage() -> dict:
    """Which sections are reachable from at least one phase, and from at least
    one tag. A section in NEITHER is dead content -- shipped but never loaded."""
    via_phase = {k for ks in PHASES.values() for k in ks}
    via_tag = {k for ks in TAGS.values() for k in ks}
    return {
        "sections": set(ALL_SECTIONS),
        "via_phase": via_phase,
        "via_tag": via_tag,
        "unreachable": set(ALL_SECTIONS) - (via_phase | via_tag),
        "orphan_tags": {k for ks in TAGS.values() for k in ks} - set(ALL_SECTIONS),
    }


def unknown_keys(phase: int | None, tag: str | None) -> list[str]:
    """Non-raising probe so callers can distinguish 'absent' from 'failed'."""
    bad = []
    if phase is not None and phase not in PHASES:
        bad.append(f"phase:{phase}")
    if tag is not None and tag not in TAGS:
        bad.append(f"tag:{tag}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcsa.loader")
    ap.add_argument("--phase", type=int)
    ap.add_argument("--tag")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--resident", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    a = ap.parse_args(argv)

    if a.coverage:
        c = coverage()
        print("sections   :", len(c["sections"]))
        print("via phase  :", len(c["via_phase"]))
        print("via tag    :", len(c["via_tag"]))
        print("UNREACHABLE:", sorted(c["unreachable"]) or "none")
        return 1 if c["unreachable"] else 0

    if a.list:
        print(list_keys())
        return 0
    if a.resident:
        print(resident())
        return 0
    if a.all:
        print(everything())
        return 0

    bad = unknown_keys(a.phase, a.tag)
    if bad:
        print(f"FAIL: unknown key(s) {bad} — refusing to emit a partial subgraph",
              file=sys.stderr)
        print("run: python -m mcsa.loader --list", file=sys.stderr)
        return 2
    if a.phase is None and a.tag is None:
        ap.error("need --phase, --tag, --all, --resident, --list, or --coverage")
    print(for_phase_and_tag(a.phase, a.tag) if a.phase and a.tag
          else for_phase(a.phase) if a.phase else for_tag(a.tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
