"""MSCA memory_cap - memory and capability management."""

from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
import json

__all__ = ["MemoryCap", "store_memory", "recall"]


class MemoryCap:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else Path(".msca_memory.json")
        self.mem: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.mem = json.loads(self.path.read_text())
            except Exception:
                self.mem = {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.mem, indent=2))
        except Exception:
            pass

    def store(self, key: str, value: Any) -> Dict[str, Any]:
        self.mem[key] = value
        self._save()
        return {"stored": True, "key": key}

    def recall(self, key: str) -> Dict[str, Any]:
        return {"key": key, "value": self.mem.get(key)}

def store_memory(key: str, value: Any) -> Dict[str, Any]:
    return MemoryCap().store(key, value)


def recall(key: str) -> Dict[str, Any]:
    return MemoryCap().recall(key)
