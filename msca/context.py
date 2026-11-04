"""MSCA context — enhanced context management.

Provides utilities for loading, merging, and managing context
for CALIBER agent operations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import loader, skills_bank, spine

__all__ = ["Context", "load_context", "merge_context"]


class Context:
    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._cache: dict[str, Any] = {}

    def load_phase(self, phase: int) -> str:
        return loader.for_phase(phase)

    def load_tag(self, tag: str) -> str:
        return loader.for_tag(tag)

    def load_union(self, phase: int, tag: str | None = None) -> str:
        if tag is None:
            return self.load_phase(phase)
        return loader.for_phase_and_tag(phase, tag)

    def load_both(self, phase: int, tag: str) -> str:
        return loader.for_phase_and_tag(phase, tag)

    def get_skills(self, query: str | None = None) -> dict[str, Any]:
        if query:
            return skills_bank.search(query)
        return skills_bank.index()

    def get_best_skills(self, limit: int | None = None) -> dict[str, Any]:
        return skills_bank.best(limit)

    def resident(self) -> str:
        return spine.RESIDENT

    def summary(self) -> dict[str, Any]:
        from . import capacity, tokens
        m = tokens.measure(spine.RESIDENT)
        return {
            "workspace": str(self.workspace),
            "resident_tokens": m["governing"],
            "skills_count": skills_bank.index()["count"],
        }


def load_context(phase: int | None = None, tag: str | None = None,
                include_skills: bool = False) -> dict[str, Any]:
    ctx = Context()
    result: dict[str, Any] = {}
    if phase:
        result[f"phase_{phase}"] = ctx.load_phase(phase)
    if tag:
        result[f"tag_{tag}"] = ctx.load_tag(tag)
    if include_skills:
        result["skills"] = ctx.get_best_skills(limit=10)
    return result


def load_union(phase: int, tag: str | None = None) -> str:
    ctx = Context()
    return ctx.load_union(phase, tag)


def merge_context(*contexts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for c in contexts:
        merged.update(c)
    return merged
