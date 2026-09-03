from __future__ import annotations

from dataclasses import dataclass

from evals.experiments.e1_discrimination import DegradationOp, degrade_composition
from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.schema.model import Composition


@dataclass
class AdversarialResult:
    original_score: float
    degraded_scores: dict[str, float]
    all_detected: bool  # All degraded <= original


def run_adversarial(comp: Composition, defaults: StyleDefaults) -> AdversarialResult:
    original = evaluate_rules(comp, defaults)
    degraded_scores = {}
    for op in DegradationOp:
        degraded = degrade_composition(comp, op)
        report = evaluate_rules(degraded, defaults)
        degraded_scores[op.value] = report.R_rule
    all_detected = all(v <= original.R_rule for v in degraded_scores.values())
    return AdversarialResult(
        original_score=original.R_rule,
        degraded_scores=degraded_scores,
        all_detected=all_detected,
    )
