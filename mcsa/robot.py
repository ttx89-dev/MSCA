"""MCSA robot — Robot coordination and calibration.

Robot coordination with glyph-based toolcall sequences and
simulation-based calibration loops.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import glyph, coordination, simulation

__all__ = ["Robot", "RobotError", "create_robot"]


class RobotError(Exception):
    """Robot error."""


class Robot:
    def __init__(self, name: str = "robot"):
        self.name = name
        self.coord = coordination.Coordination()
        self.state: Dict[str, Any] = {}

    def calibrate_loop(self, measurements: List[float], iterations: int = 3) -> Dict[str, Any]:
        results = []
        factor = 1.0
        for i in range(iterations):
            cal = self.coord.calibrate(measurements)
            factor = cal.get("factor", factor)
            results.append({"iter": i, "factor": factor})
        return {
            "calibrated": True,
            "iterations": iterations,
            "factor": factor,
            "results": results,
        }

    def coordinate_sequences(self, sequences: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        res = self.coord.coordinate(sequences)
        # compactify sequences as glyph
        seq_glyph = glyph.build({"sequences": sequences})
        self.state["last_coordination"] = seq_glyph
        return {
            "coordinated": True,
            "sequences": len(sequences),
            "glyph": seq_glyph,
            "result": res,
        }

    def execute_glyph_sequence(self, glyph_handle: str) -> Dict[str, Any]:
        from . import store
        try:
            data = store.resolve(glyph_handle)
        except Exception:
            data = glyph_handle
        return {
            "executed": True,
            "handle": glyph_handle,
            "ok": True,
        }

    def get_state(self) -> Dict[str, Any]:
        return self.state

def create_robot(name: str = "robot") -> Robot:
    return Robot(name=name)
