from __future__ import annotations

from dataclasses import dataclass

from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.schema.model import Composition


@dataclass
class ConsistencyResult:
    rule_deterministic: bool
    rule_range: dict[str, float]
    judge_stability: dict[str, float] | None = None


def check_rule_determinism(
    comp: Composition, defaults: StyleDefaults, runs: int = 3
) -> ConsistencyResult:
    scores = []
    for _ in range(runs):
        report = evaluate_rules(comp, defaults)
        scores.append(report.R_rule)
    rule_range = {
        "min": min(scores),
        "max": max(scores),
        "range": max(scores) - min(scores),
        "std": (sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)) ** 0.5,
    }
    return ConsistencyResult(
        rule_deterministic=rule_range["range"] == 0.0,
        rule_range=rule_range,
    )
