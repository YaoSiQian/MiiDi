from __future__ import annotations

from dataclasses import dataclass, field

from miidi.eval.axes import (
    AxisResult,
    axis_dynamics,
    axis_format,
    axis_harmony,
    axis_rhythm,
    axis_structure,
    axis_voice,
)
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.eval.gates import gate_balance, gate_density, gate_repetition, gate_spread
from miidi.schema.model import Composition
from miidi.schema.validate import Violation

AXIS_WEIGHTS = {
    "harmony": 0.30,
    "voice": 0.20,
    "rhythm": 0.20,
    "structure": 0.20,
    "dynamics": 0.10,
}
GATE_NAMES = ("repetition", "density", "balance", "spread")


@dataclass(frozen=True)
class RuleReport:
    invalid: bool
    R_rule: float
    axes: dict[str, AxisResult] = field(default_factory=dict)
    gates: dict[str, float] = field(default_factory=dict)
    violations: tuple[Violation, ...] = ()

    def to_dict(self) -> dict:
        return {
            "invalid": self.invalid,
            "R_rule": round(self.R_rule, 6),
            "axes": {
                k: {"score": round(v.score, 6), "details": v.details} for k, v in self.axes.items()
            },
            "gates": {k: round(v, 6) for k, v in self.gates.items()},
            "violations": [v.__dict__ for v in self.violations],
        }


def evaluate_rules(comp: Composition, defaults: StyleDefaults | None = None) -> RuleReport:
    fmt_score, viols = axis_format(comp)
    if fmt_score < 1.0:
        return RuleReport(invalid=True, R_rule=0.0, violations=tuple(viols))
    ctx = EvaluationContext.from_composition(comp, defaults)
    axes = {
        "harmony": axis_harmony(ctx),
        "voice": axis_voice(ctx),
        "rhythm": axis_rhythm(ctx),
        "structure": axis_structure(ctx),
        "dynamics": axis_dynamics(ctx),
    }
    base = sum(AXIS_WEIGHTS[k] * axes[k].score for k in AXIS_WEIGHTS)
    gates = {
        "repetition": gate_repetition(ctx),
        "density": gate_density(ctx),
        "balance": gate_balance(ctx),
        "spread": gate_spread(ctx),
    }
    multiplier = 1.0
    for v in gates.values():
        multiplier *= max(v, 0.0)
    r = max(0.0, min(100.0, 100.0 * base * multiplier))
    return RuleReport(invalid=False, R_rule=r, axes=axes, gates=gates)
