"""MSCA env — LLM/dev environment management.

Environment configuration, calibration, and coordination setup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

__all__ = ["Env", "load_env", "get_env"]


class Env:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path.cwd()
        self._config: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return os.environ.get(key, self._config.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def calibrate(self) -> Dict[str, Any]:
        return {
            "calibrated": True,
            "root": str(self.root),
            "env_count": len(self._config),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": str(self.root),
            "config": self._config,
        }


def load_env() -> Env:
    return Env()


def get_env(key: str, default: Any = None) -> Any:
    return Env().get(key, default)


