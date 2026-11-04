"""MCSA glyph utilities — enhanced glyph operations.

Provides utilities for working with glyphs/handles, complementing the
store module. Focuses on glyph operations mentioned in instruments:
build, compact, diff, explain, fold, intersect, lint, map, union.

All operations are loud-fail, testable, replicable.
"""

from __future__ import annotations

import json
from typing import Any

from . import store

__all__ = ["GlyphError", "build", "compact", "diff", "explain", "fold",
           "intersect", "lint", "map_op", "union"]


class GlyphError(Exception):
    """Glyph operation error."""


def build(obj: dict[str, Any] | list[Any] | str | bytes) -> str:
    """Build a glyph handle from content."""
    if isinstance(obj, dict) or isinstance(obj, list):
        content = json.dumps(obj, sort_keys=True, separators=(',', ':'))
    elif isinstance(obj, str):
        content = obj
    elif isinstance(obj, bytes):
        content = obj.decode('utf-8', errors='replace')
    else:
        raise GlyphError(f"cannot build glyph from {type(obj)}")
    return store.mint(content, kind="G")


def compact(handles: list[str]) -> str:
    """Compact multiple glyphs into one combined glyph."""
    if not handles:
        raise GlyphError("cannot compact empty handles list")
    contents = []
    for h in handles:
        contents.append(store.resolve(h))
    combined = "\n---\n".join(contents)
    return store.mint(combined, kind="G")


def diff(h1: str, h2: str) -> dict[str, Any]:
    """Diff two glyphs, returning structural diff info."""
    c1 = store.resolve(h1)
    c2 = store.resolve(h2)
    if c1 == c2:
        return {"equal": True, "added": [], "removed": [], "common": len(c1.splitlines())}
    lines1 = set(c1.splitlines())
    lines2 = set(c2.splitlines())
    added = sorted(list(lines2 - lines1))
    removed = sorted(list(lines1 - lines2))
    common = lines1 & lines2
    return {
        "equal": False,
        "h1_lines": len(c1.splitlines()),
        "h2_lines": len(c2.splitlines()),
        "h1_bytes": len(c1),
        "h2_bytes": len(c2),
        "added": added[:200],  # cap for readability
        "removed": removed[:200],
        "added_count": len(added),
        "removed_count": len(removed),
        "common_count": len(common),
    }


def explain(h: str) -> dict[str, Any]:
    """Explain a glyph - metadata about its contents."""
    c = store.resolve(h)
    return {
        "handle": h,
        "bytes": len(c),
        "lines": len(c.splitlines()),
        "chars": len(c),
    }


def fold(handles: list[str], op: str = "concat") -> str:
    """Fold over glyph handles."""
    if not handles:
        raise GlyphError("cannot fold empty list")
    if op == "concat":
        return compact(handles)
    elif op == "join":
        contents = [store.resolve(h) for h in handles]
        return store.mint("\n".join(contents), kind="G")
    elif op == "merge":
        contents = [store.resolve(h) for h in handles]
        lines = set()
        for c in contents:
            lines.update(c.splitlines())
        return store.mint("\n".join(sorted(lines)), kind="G")
    raise GlyphError(f"unknown fold op: {op}")


def intersect(h1: str, h2: str) -> str:
    """Find intersection of contents (line-based)."""
    c1 = set(store.resolve(h1).splitlines())
    c2 = set(store.resolve(h2).splitlines())
    inter = c1 & c2
    return store.mint("\n".join(sorted(inter)), kind="G")


def lint(h: str) -> dict[str, Any]:
    """Lint a glyph for issues."""
    c = store.resolve(h)
    issues = []
    if len(c.strip()) == 0:
        issues.append("empty content")
    if len(c) > 1000000:  # 1MB threshold
        issues.append("very large glyph (>1MB)")
    return {"ok": len(issues) == 0, "issues": issues}


def map_op(h: str, transform: str = "identity") -> str:
    """Map operation over glyph content."""
    c = store.resolve(h)
    if transform == "identity":
        return store.mint(c, kind="G")
    elif transform == "lower":
        return store.mint(c.lower(), kind="G")
    elif transform == "upper":
        return store.mint(c.upper(), kind="G")
    elif transform == "strip":
        return store.mint(c.strip(), kind="G")
    elif transform == "sort_lines":
        lines = c.splitlines()
        return store.mint("\n".join(sorted(lines)), kind="G")
    elif transform == "reverse_lines":
        lines = c.splitlines()
        return store.mint("\n".join(reversed(lines)), kind="G")
    else:
        raise GlyphError(f"unknown transform: {transform}")


def union(h1: str, h2: str) -> str:
    """Union of contents (line-based)."""
    c1 = set(store.resolve(h1).splitlines())
    c2 = set(store.resolve(h2).splitlines())
    unioned = c1 | c2
    return store.mint("\n".join(sorted(unioned)), kind="G")
