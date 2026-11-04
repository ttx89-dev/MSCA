"""MSCA capability - capability management for the agent stack."""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["Capability", "register", "list_caps"]


class Capability:
    def __init__(self):
        self.caps: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        self.caps[name] = meta
        return {"registered": True, "name": name}

    def list(self) -> Dict[str, Any]:
        return {"capabilities": self.caps, "count": len(self.caps)}

def register(name: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return Capability().register(name, meta or {})


def list_caps() -> Dict[str, Any]:
    return Capability().list()
