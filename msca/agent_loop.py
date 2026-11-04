"""MSCA agent_loop - Agent loop implementation."""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["AgentLoop", "run_loop"]


class AgentLoop:
    def __init__(self, max_iter: int = 10):
        self.max_iter = max_iter
        self.state = {}

    def step(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "step": 1,
            "output": input_data,
        }

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        results = []
        for i in range(self.max_iter):
            res = self.step(input_data)
            results.append(res)
            if res.get("done"):
                break
        return {
            "done": True,
            "iterations": len(results),
            "results": results,
        }

def run_loop(input_data: Dict[str, Any], max_iter: int = 10) -> Dict[str, Any]:
    return AgentLoop(max_iter=max_iter).run(input_data)
