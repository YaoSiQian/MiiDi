from __future__ import annotations

from dataclasses import dataclass

from miidi.eval.judge import JudgeReport
from miidi.eval.score import RuleReport


@dataclass(frozen=True)
class CompositeReport:
    composite: float
    R_rule: float
    Judge_mean: float
    J1: float
    J2: float
    J3: float

    def to_dict(self) -> dict:
        return {
            "composite": round(self.composite, 2),
            "R_rule": round(self.R_rule, 2),
            "Judge_mean": round(self.Judge_mean, 2),
            "J1": round(self.J1, 2),
            "J2": round(self.J2, 2),
            "J3": round(self.J3, 2),
        }


def compute_composite(rule: RuleReport, judge: JudgeReport) -> CompositeReport:
    if rule.invalid:
        return CompositeReport(
            composite=0.0, R_rule=0.0, Judge_mean=0.0, J1=judge.J1, J2=judge.J2, J3=judge.J3
        )
    judge_mean = (judge.J1 + judge.J2 + judge.J3) / 3.0
    composite = 0.6 * rule.R_rule + 0.4 * judge_mean
    return CompositeReport(
        composite=composite,
        R_rule=rule.R_rule,
        Judge_mean=judge_mean,
        J1=judge.J1,
        J2=judge.J2,
        J3=judge.J3,
    )
