"""MCSA tools_seq - Toolcall sequence management for the agent stack."""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["ToolSeq", "create_sequence", "execute_sequence"]


class ToolSeq:
    def __init__(self):
        self.sequence: List[Dict[str, Any]] = []

    def add_step(self, tool: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        step = {"tool": tool, "args": args or {}}
        self.sequence.append(step)
        return step

    def build(self) -> List[Dict[str, Any]]:
        return list(self.sequence)

    def clear(self) -> None:
        self.sequence.clear()

def create_sequence() -> ToolSeq:
    return ToolSeq()


def execute_sequence(seq: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"executed": True, "steps": len(seq), "ok": True}
