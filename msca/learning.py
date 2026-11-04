"""MSCA learning — Learning and adaptation for the agent stack."""

from __future__ import annotations

from typing import Any, Dict, List
import json
from pathlib import Path

__all__ = ["Learning", "learn", "adapt"]


class Learning:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else Path(".msca_learning.json")
        self.history: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.history = json.loads(self.path.read_text())
            except Exception:
                self.history = []

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.history, indent=2))
        except Exception:
            pass

    def learn(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        exp = {**experience, "idx": len(self.history)}
        self.history.append(exp)
        self._save()
        return {"learned": True, "exp": exp}

    def adapt(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "adapted": True,
            "history_count": len(self.history),
            "context": context,
        }

def learn(experience: Dict[str, Any]) -> Dict[str, Any]:
    return Learning().learn(experience)


def adapt(context: Dict[str, Any]) -> Dict[str, Any]:
    return Learning().adapt(context)
