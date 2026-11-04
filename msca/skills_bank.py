"""Skills bank — deterministic index of local skills."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()

CANDIDATE_DIRS = [
    HOME / ".claude" / "skills",
    HOME / ".config" / "opencode" / "skills",
    ROOT / ".claude" / "skills",
    ROOT / ".opencode" / "skills",
    ROOT / ".agents" / "skills",
    ROOT / "agents" / "skills",
    HOME / ".agents" / "skills",
]


def _find_skill_md(base: Path) -> list[Path]:
    if not base.exists() or not base.is_dir():
        return []
    out = []
    for p in base.rglob("SKILL.md"):
        out.append(p)
    return out


def _parse_name(txt: str) -> str:
    m = re.search(r"^name:\s*(.+)$", txt, flags=re.M)
    return m.group(1).strip() if m else ""


def _parse_description(txt: str) -> str:
    m = re.search(r"^description:\s*(.+)$", txt, flags=re.M | re.S)
    if m:
        return " ".join(m.group(1).split())
    for line in txt.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("---"):
            return s
    return ""


def _parse_tags(txt: str) -> list[str]:
    m = re.search(r"^tags:\s*\[(.*?)\]", txt, flags=re.M | re.S)
    if m:
        return [t.strip().strip('"').strip("'") for t in m.group(1).split(",") if t.strip()]
    return []


def index(root: Path | None = None) -> dict[str, Any]:
    roots = [Path(root)] if root else CANDIDATE_DIRS
    skills = []
    seen = set()
    for base in roots:
        for md in _find_skill_md(base):
            try:
                txt = md.read_text(errors="replace")
            except Exception:
                continue
            name = _parse_name(txt) or md.parent.name
            if name in seen:
                continue
            seen.add(name)
            skills.append({
                "name": name,
                "description": _parse_description(txt),
                "tags": _parse_tags(txt),
                "location": str(md.resolve()),
                "dir": str(md.parent.resolve()),
            })
    skills.sort(key=lambda x: x["name"].lower())
    return {"skills": skills, "count": len(skills)}


def search(query: str, root: Path | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    q = (query or "").lower()
    tagset = set(t.lower() for t in (tags or []))
    idx = index(root)
    if not q and not tagset:
        return idx
    res = []
    for s in idx["skills"]:
        hay = " ".join([s["name"], s["description"], " ".join(s["tags"])]).lower()
        skill_tags = set(t.lower() for t in s["tags"])
        match = True
        if tagset and not tagset.intersection(skill_tags):
            match = False
        if q and q not in hay:
            match = False
        if match:
            res.append(s)
    res.sort(key=lambda x: x["name"].lower())
    return {"skills": res, "count": len(res), "query": query}


def search_by_tags(tags: list[str], root: Path | None = None) -> dict[str, Any]:
    return search("", root=root, tags=tags)

PRIORITY = [
    "efe-optibest-engineer",
    "efe-optibest-refiner",
    "points-delegation",
    "points-encoding",
    "rust-best-practices",
    "senior-architect",
    "transitions-dev",
    "self-eval",
    "transitions-polish",
]


def best(limit: int | None = None) -> dict[str, Any]:
    idx = index()
    by_name = {x["name"]: x for x in idx["skills"]}
    out = []
    for name in PRIORITY:
        if name in by_name:
            out.append(by_name[name])
    # also include any matches for points/harness not in priority
    seen = set(x["name"] for x in out)
    for s in idx["skills"]:
        if s["name"] in seen:
            continue
        hay = " ".join([s["name"], s["description"]]).lower()
        if any(k in hay for k in ["points", "harness", "caliber", "msca"]):
            out.append(s)
            seen.add(s["name"])
    if limit:
        out = out[:limit]
    return {"skills": out, "count": len(out)}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(index(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--best":
        print(json.dumps(best(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(index(), indent=2))
    else:
        idx = index()
        for sk in idx["skills"][:30]:
            print(f"- {sk['name']}: {sk['description'][:80]}")
        if idx["count"] > 30:
            print(f"... ({idx['count']-30} more)")
