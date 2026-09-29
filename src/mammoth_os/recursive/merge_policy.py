from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .node import RecursiveNode


@dataclass
class MergeResult:
    artifacts: dict[str, Any]
    critique: Any = None
    selected_node_id: str | None = None


class MergePolicy(Protocol):
    def merge(self, nodes: list[RecursiveNode]) -> MergeResult: ...


class ConfidenceWeightedMergePolicy:
    """Select the highest-confidence node; ties retain the input order."""

    def merge(self, nodes: list[RecursiveNode]) -> MergeResult:
        if not nodes:
            return MergeResult({})
        best = max(
            enumerate(nodes),
            key=lambda item: (
                item[1].critique.confidence if item[1].critique is not None else 0.0,
                -item[0],
            ),
        )[1]
        return MergeResult(dict(best.artifacts), best.critique, best.id)
