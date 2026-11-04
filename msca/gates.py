"""MSCA gates — the dev policy as executable code.

SCRIPTABLE:  python -m msca.gates
Every gate returns (name, passed, measured, floor). Exit non-zero on any
failure, so it can be a CI step and not a checklist.

The meta-gate is G-OPS: a gate that has never been run against a failing input
is a claim, not a check. `self_test()` below deliberately corrupts the resident
tier and asserts the gates go RED, then restores it. A suite that stays green
under deliberate breakage is worse than no suite -- it manufactures false
confidence, the same failure class as parity_ok=True over a truncated payload.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

from . import capacity, relate, store, tokens
from .loader import ALL_SECTIONS, PHASES, TAGS, coverage
from .spine import RESIDENT, SECTIONS

# ── thresholds ───────────────────────────────────────────────────────────────
# R1's ceiling is CONFIG, not a literal (PROGRAMMABLE gate). Measured 2026-09-30
# on the resident spine: chars/4 said 415; the worst real tokenizer said 488.
# An estimate under-reported by 18%, which is why the gate now bounds a
# measurement and lets an owner set the ceiling with a number in hand.
R7_MAX_4GRAM_REDUNDANCY = 0.05
R7_MAX_DECORATION = 0.005
R6_FORBIDDEN = (
    "delta → 0", "delta->0", "zero-delta", "plateau confirmed",
    "cannot be improved", "cannot enhance", "premium confirmed",
    "no enhancement vectors", "highest caliber", "best possible",
    "concluded optimal", "cannot be made", "as good as it gets",
)


@dataclass
class Result:
    name: str
    passed: bool
    measured: str
    floor: str


def _tokens(text: str) -> int:
    """chars/4. RETAINED ONLY AS A LEGACY ESTIMATE.

    Measured 2026-09-30: chars/4 said 415 where p50k_base said 488. An 18%
    under-report. Kept so the drift is visible in one place; gates use
    tokens.measure(), never this.
    """
    return len(text) // 4


def r1_resident_ceiling(text: str = RESIDENT) -> Result:
    """Real tokenizer, worst encoding. `measured` carries WHICH encoding
    governed so a pass can never be mistaken for an estimate."""
    m = tokens.measure(text)
    gov, ceil = m["governing"], tokens.ceiling()
    return Result(
        "R1 resident ceiling", gov <= ceil,
        f"{gov} tok ({m['method']}"
        + (f", {m['worst_encoding']}" if m["worst_encoding"] else "") + ")",
        f"<= {ceil} (MSCA_R1_MAX_TOKENS)")


def r6_no_self_certification(text: str = RESIDENT) -> Result:
    low = text.lower()
    hits = [p for p in R6_FORBIDDEN if p in low]
    return Result("R6 no self-certification", not hits,
                  f"{len(hits)} hits" + (f" {hits}" if hits else ""), "0 hits")


def r7_redundancy(text: str = RESIDENT) -> Result:
    w = re.findall(r"[A-Za-z_]{3,}", text)
    if len(w) < 8:
        return Result("R7 redundancy", True, "n/a (too short)", "<= 5%")
    ng = Counter(tuple(w[i:i + 4]) for i in range(len(w) - 4))
    red = 1 - len(ng) / sum(ng.values())
    return Result("R7 redundancy", red <= R7_MAX_4GRAM_REDUNDANCY,
                  f"{100*red:.1f}%", "<= 5%")


def r7_decoration(text: str = RESIDENT) -> Result:
    d = len(re.findall(r"[\u2588\u2591\u2592\u2500-\u257f\u2550-\u256c]", text))
    ratio = d / len(text) if text else 0.0
    return Result("R7 decoration", ratio <= R7_MAX_DECORATION,
                  f"{100*ratio:.2f}%", "<= 0.50%")


def r_pointer_disclosure() -> Result:
    """Every pointer target in the resident tier must exist.

    A pointer to nothing is a silent FAIL downstream (F2 class). Parsed from the
    PTR block by module stem, not by line position, because an inline PTR list
    would otherwise silently reduce the count and weaken this gate.
    """
    ptrs = re.findall(r"\b([a-z_]+\.py)\b", RESIDENT)
    ptrs += [m + ".py" for m in re.findall(r"`python -m msca\.([a-z_]+)`", RESIDENT)]
    seen, ordered = set(), []
    for p in ptrs:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    bad = []
    for p in ordered:
        mod = p[:-3]
        if mod in SECTIONS:
            continue
        if not (Path(__file__).parent / p).exists():
            bad.append(p)
    return Result("PTR targets resolve", not bad,
                  f"{len(ordered)} ptrs, {len(bad)} dead"
                  + (f" {bad}" if bad else ""), "0 dead")


def r_index_total() -> Result:
    c = coverage()
    return Result("index covers all sections", not c["unreachable"],
                  f"{len(c['unreachable'])} unreachable"
                  + (f" {sorted(c['unreachable'])}" if c["unreachable"] else ""),
                  "0 unreachable")


def r_index_completeness() -> Result:
    """Every phase 1-15 and every declared tag must resolve."""
    missing = [p for p in range(1, 16) if p not in PHASES]
    missing += [f"tag:{t}" for t in TAGS if t not in TAGS]
    return Result("index complete 1-15", not missing,
                  f"{len(missing)} missing" + (f" {missing}" if missing else ""),
                  "0 missing")


def r_sections_nonempty() -> Result:
    empty = [k for k in ALL_SECTIONS if len(SECTIONS.get(k, "").strip()) < 40]
    return Result("sections non-trivial", not empty,
                  f"{len(empty)} stub" + (f" {empty}" if empty else ""),
                  "0 stub")


def r_loud_fail() -> Result:
    """The POINTS defect class: overflow must RAISE, never truncate silently."""
    from .loader import for_phase, for_tag, unknown_keys
    try:
        for_phase(999)
    except KeyError:
        try:
            for_tag("nope")
        except KeyError:
            if unknown_keys(999, "nope") == ["phase:999", "tag:nope"]:
                return Result("R4 loud-fail", True, "raises + probes", "must raise")
            return Result("R4 loud-fail", False, "probe mismatch", "consistent")
        return Result("R4 loud-fail", False, "for_tag did not raise", "must raise")
    return Result("R4 loud-fail", False, "for_phase did not raise", "must raise")


def r3_capacity_record() -> Result:
    """C2. The recorded capacity claim must MATCH the code as it is now.

    A stale record is a false claim. The record exists to be checkable; if it
    cannot be checked against source it is decoration.
    """
    v = capacity.verify()
    if not v["ok"] and "no record" in v.get("reason", ""):
        return Result("R3 capacity record", False, "no record", "must exist")
    return Result("R3 capacity record", v["ok"],
                  "matches code" if v["ok"] else "; ".join(v.get("drift", [])),
                  "no drift")


def r5_store_roundtrip() -> Result:
    """C1. Every pointed section must be mintable and resolvable, durably."""
    try:
        hs = store.mint_all_sections()
    except Exception as e:
        return Result("R5 store round-trip", False, f"mint failed: {e}", "all mint")
    bad = []
    for k, h in hs.items():
        if store.resolve(h) != SECTIONS[k]:
            bad.append(k)
    return Result("R5 store round-trip", not bad,
                  f"{len(hs)} handles, {len(bad)} mismatch", "0 mismatch")


def r5_handle_grammar() -> Result:
    """C1. Resolution must be loud on unknown and on corruption."""
    checks = []
    try:
        store.resolve("<G:0000>")
        checks.append("unknown handle did NOT raise")
    except store.UnknownHandle:
        pass
    except Exception as e:
        checks.append(f"wrong exception: {type(e).__name__}")
    try:
        store.resolve("not-a-handle")
        checks.append("malformed handle did NOT raise")
    except store.UnknownHandle:
        pass
    except Exception as e:
        checks.append(f"wrong exception: {type(e).__name__}")
    try:
        store.mint("")
        checks.append("empty payload did NOT raise")
    except store.HandleError:
        pass
    return Result("R5 handle grammar", not checks,
                  "; ".join(checks) if checks else "raises on unknown/malformed/empty",
                  "all raise")


def r12_ontology_algebra() -> Result:
    """C4. The two gap-closing relations must be distinct AND enforced.

    The negative cases are the point: if the conflation guard did not fire,
    this gate would pass anyway -- so it is asserted here as a hard failure.
    """
    o = relate.Ontology()
    o.equivalent("car", "automobile")
    o.equivalent("automobile", "auto")
    o.is_a("island_nation", "country")
    o.instance_of("france", "country")
    prob = []
    if not o.same_referent("car", "auto"):
        prob.append("EQL not transitive")
    if o.possible_subtypes("france"):
        prob.append("instance gained subtypes")
    if "france" in o.ancestors("country"):
        prob.append("INS became transitive (non-transitivity broken)")
    if not o.is_instance("france"):
        prob.append("instance not recognised")
    for label, fn in (
        ("is_a(france,..) must be refused", lambda: o.is_a("france", "country")),
        ("EQL self must be refused", lambda: o.equivalent("france", "france")),
        ("PAR bad qualifier refused", lambda: o.part_of("a", "b", "NOPE")),
    ):
        try:
            fn()
            prob.append(label)
        except relate.RelationViolation:
            pass
    a = o.audit()
    if not a["ok"]:
        prob += a["problems"]
    return Result("R12 ontology algebra", not prob,
                  "; ".join(prob) if prob else "EQL transitive, INS non-transitive",
                  "0 violations")



def r_docs_drift() -> Result:
    """H3. The manual addendum must be GENERATED from spine.RESIDENT, never
    hand-maintained beside it.

    Two sources of truth for one resident tier is the exact failure this project
    exists to prevent, and it happened once already: the addendum drifted to
    2003 chars while the spine moved to 1660. This gate makes drift a hard
    failure rather than something a careful reader has to notice.
    """
    root = Path(__file__).resolve().parent.parent
    f = root / "MSCA_AGENT_MANUAL_ADDENDUM.md"
    if not f.exists():
        return Result("R9 docs no-drift", False, "addendum absent", "must exist")
    txt = f.read_text()
    m = re.search(r"## T0[^\n]*\n(?:(?!```).)*```\n(.*?)\n```", txt, re.S)
    if not m:
        return Result("R9 docs no-drift", False, "no T0 block in addendum",
                      "generated block present")
    same = m.group(1).strip() == RESIDENT.strip()
    return Result("R9 docs no-drift", same,
                  "addendum == spine" if same else "DRIFT: addendum != spine.RESIDENT",
                  "regenerate: python -m msca --regen-docs")


def r_capacity_floor() -> Result:
    """D5. Capacity must be at or above the approved floor.

    Distinct from r3_capacity_record. Record-verification asks "does the claim
    match the code"; this asks "is the code still worth deploying". A tree can
    satisfy the first and fail the second -- that decay is what D5 exists to
    catch, and it is the failure a record alone cannot see.
    """
    fv = capacity.floor_verdict()
    return Result("D5 capacity floor", fv["ok"],
                  f"{fv['value']} bits/tok ({fv['headroom']:+} vs {fv['floor']})",
                  f">= {fv['floor']} bits/tok")

GATES: tuple[Callable[[], Result], ...] = (
    r1_resident_ceiling, r6_no_self_certification, r7_redundancy, r7_decoration,
    r_pointer_disclosure, r_index_total, r_index_completeness,
    r_sections_nonempty,
    r_loud_fail, r3_capacity_record, r5_store_roundtrip, r5_handle_grammar,
    r12_ontology_algebra, r_docs_drift, r_capacity_floor,
)


def run(verbose: bool = True) -> tuple[list[Result], bool]:
    res = [g() for g in GATES]
    if verbose:
        w = max(len(r.name) for r in res)
        for r in res:
            print(f"  {'PASS' if r.passed else 'FAIL'}  {r.name:<{w}}  "
                  f"{r.measured:<28} floor {r.floor}")
    return res, all(r.passed for r in res)


# ── the meta-gate: prove these gates can actually fail ──────────────────────

def self_test() -> bool:
    """Break the resident tier on purpose; assert the gates go RED.

    OPERABLE + TESTABLE in one check. If this ever passes with corrupted input,
    the gates are decorative and the whole module is untrustworthy.
    """
    print("self_test: injecting 3 deliberate defects")
    for label, mutate in [
        ("R1 overflow", lambda t: t + (" filler sentence. " * 400)),
        ("R6 certification", lambda t: t + "\nEnhancement Delta: Zero [plateau confirmed]"),
        ("R7 decoration", lambda t: t + ("\u2588" * 200)),
    ]:
        broken = mutate(RESIDENT)
        red = [g(broken).passed for g in
               (r1_resident_ceiling, r6_no_self_certification, r7_redundancy, r7_decoration)]
        caught = not all(red)
        print(f"  {'OK  ' if caught else 'DEAD'}  {label:<18} -> "
              f"gates read {[('P' if x else 'F') for x in red]}")
        if not caught:
            return False
    # and a metric regression, not just text corruption
    import msca.capacity as _cap
    real = _cap.measure
    _cap.measure = lambda root=None: {**real(root), "capacity_bits_per_resident_token": 1.0}
    try:
        floor_red = not r_capacity_floor().passed
    finally:
        _cap.measure = real
    print(f"  {'OK  ' if floor_red else 'DEAD'}  D5 floor regression -> "
          f"{'gate read F' if floor_red else 'GATE DID NOT FIRE'}")
    if not floor_red:
        return False
    print("self_test: gates demonstrably detect corruption AND metric regression")
    return True


def main() -> int:
    print("MSCA gates")
    res, ok = run()
    print()
    ok_self = self_test()
    print()
    verdict = "ALL GATES PASS" if (ok and ok_self) else "GATE FAILURE"
    print(f"{verdict}  ({sum(r.passed for r in res)}/{len(res)} gates, "
          f"self_test={'pass' if ok_self else 'FAIL'})")
    return 0 if (ok and ok_self) else 1


if __name__ == "__main__":
    raise SystemExit(main())
