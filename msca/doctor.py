"""MSCA doctor — CALIBER environment health checks.

Runs comprehensive health checks across the CALIBER local environment:
gates, capacity, store, coverage, skills. Returns structured results
and exit codes suitable for scripting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import capacity, gates, loader, skills_bank, spine, store, tokens

__all__ = ["CheckResult", "check_gates", "check_capacity", "check_store",
           "check_coverage", "check_skills", "check_resident",
           "check_agent_drift", "run_all", "format_report"]


class CheckResult:
    def __init__(self, name: str, ok: bool, message: str = "",
                 details: Dict[str, Any] | None = None):
        self.name = name
        self.ok = ok
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "message": self.message,
            "details": self.details,
        }


def check_resident() -> CheckResult:
    try:
        m = tokens.measure(spine.RESIDENT)
        ok = m["governing"] <= tokens.ceiling()
        return CheckResult(
            "resident_budget",
            ok,
            f"{m['governing']} tok ({m['worst_encoding']}) <= {tokens.ceiling()}",
            {
                "governing": m["governing"],
                "ceiling": tokens.ceiling(),
                "method": m["method"],
                "worst_encoding": m["worst_encoding"],
            },
        )
    except Exception as e:
        return CheckResult("resident_budget", False, f"error: {e}")


def check_gates() -> CheckResult:
    try:
        res, ok_all = gates.run(verbose=False)
        return CheckResult(
            "gates",
            ok_all,
            f"{sum(r.passed for r in res)}/{len(res)} gates passed",
            {
                "passed": sum(r.passed for r in res),
                "total": len(res),
            },
        )
    except Exception as e:
        return CheckResult("gates", False, f"error: {e}")


def check_capacity() -> CheckResult:
    try:
        v = capacity.verify()
        fv = capacity.floor_verdict()
        ok = v["ok"] and fv["ok"]
        msg = f"verify={'ok' if v['ok'] else 'drift'} floor={'ok' if fv['ok'] else 'below'}"
        return CheckResult(
            "capacity",
            ok,
            msg,
            {
                "verify_ok": v["ok"],
                "floor_ok": fv["ok"],
                "value": fv["value"],
                "floor": fv["floor"],
                "headroom": fv["headroom"],
            },
        )
    except Exception as e:
        return CheckResult("capacity", False, f"error: {e}")


def check_store() -> CheckResult:
    try:
        hs = store.list_()
        st = store.stats()
        all_resolve_ok = True
        try:
            store.mint_all_sections()
        except Exception:
            all_resolve_ok = False
        ok = len(hs) > 0 and all_resolve_ok
        return CheckResult(
            "store",
            ok,
            f"{st['handles']} handles, width={st['width']}",
            {
                "handles": st["handles"],
                "width": st["width"],
                "bytes": st["bytes"],
                "all_resolve_ok": all_resolve_ok,
            },
        )
    except Exception as e:
        return CheckResult("store", False, f"error: {e}")


def check_coverage() -> CheckResult:
    try:
        c = loader.coverage()
        ok = len(c["unreachable"]) == 0 and len(c["orphan_tags"]) == 0
        msg = f"unreachable={len(c['unreachable'])} orphan_tags={len(c['orphan_tags'])}"
        return CheckResult(
            "coverage",
            ok,
            msg,
            {
                "sections": len(c["sections"]),
                "via_phase": len(c["via_phase"]),
                "via_tag": len(c["via_tag"]),
                "unreachable": sorted(list(c["unreachable"])),
                "orphan_tags": sorted(list(c["orphan_tags"])),
            },
        )
    except Exception as e:
        return CheckResult("coverage", False, f"error: {e}")


def check_skills() -> CheckResult:
    try:
        idx = skills_bank.index()
        res = skills_bank.best(limit=5)
        ok = idx["count"] > 0
        return CheckResult(
            "skills",
            ok,
            f"{idx['count']} indexed, {res['count']} best",
            {
                "count": idx["count"],
                "best_count": res["count"],
            },
        )
    except Exception as e:
        return CheckResult("skills", False, f"error: {e}")


def check_agent_drift() -> CheckResult:
    try:
        ROOT = Path(__file__).resolve().parent.parent
        # 2026-11-05: the deployment-grade manual is tracked at the repository
        # root (moved out of .opencode/agents/); --regen-agent still writes its
        # minimal render to that gitignored scratch path.
        AGENT = ROOT / "CALIBER.md"
        if not AGENT.exists():
            return CheckResult("agent_drift", False,
                               "CALIBER.md missing (deployment-grade manual at repository root)")
        from .spine import RESIDENT
        norm = lambda t: [l.rstrip() for l in t.splitlines() if l.strip()]
        want, have = norm(RESIDENT.strip()), norm(AGENT.read_text())
        ok = any(have[i:i + len(want)] == want
                 for i in range(max(1, len(have) - len(want) + 1)))
        msg = ("resident tier in sync with spine" if ok
               else "DRIFT: resident tier differs from spine; "
                    "reconcile CALIBER.md surgically (see README)")
        return CheckResult("agent_drift", ok, msg)
    except Exception as e:
        return CheckResult("agent_drift", False, f"error: {e}")


def run_all() -> Tuple[bool, List[CheckResult], Dict[str, Any]]:
    checks = [
        check_resident(),
        check_gates(),
        check_capacity(),
        check_store(),
        check_coverage(),
        check_skills(),
        check_agent_drift(),
    ]
    ok_all = all(c.ok for c in checks)
    summary = {
        "ok": ok_all,
        "passed": sum(1 for c in checks if c.ok),
        "failed": sum(1 for c in checks if not c.ok),
        "total": len(checks),
    }
    return ok_all, checks, summary


def format_report(ok_all: bool, checks: List[CheckResult],
                  summary: Dict[str, Any], verbose: bool = False) -> str:
    lines = []
    status = "PASS" if ok_all else "FAIL"
    lines.append(f"MSCA DOCTOR: {status} ({summary['passed']}/{summary['total']})")
    lines.append("-" * 60)
    for c in checks:
        icon = "+" if c.ok else "-"
        lines.append(f"{icon} {c.name:20s} {c.message}")
    return "\n".join(lines)
