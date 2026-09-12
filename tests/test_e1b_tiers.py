from __future__ import annotations

import pytest

from evals.experiments.e1_discrimination import DegradationOp, degrade_composition
from evals.experiments.e1b_tiers import MILD_OPS, SEVERE_OPS, degrade_stacked
from evals.experiments.stats import spearman
from miidi.eval.score import evaluate_rules
from miidi.schema.model import Composition
from miidi.skills.loader import StyleDefaults

MELODY_PITCHES = [74, 76, 77, 79, 77, 76, 74, 72, 74, 76, 77, 74, 72, 74, 76, 72]


def _comp() -> Composition:
    return Composition(
        meta={"bpm": 120},
        structure=[{"name": "A", "start_bar": 0, "bars": 16}],
        tracks=[
            {
                "name": "Lead",
                "role": "melody",
                "program": 73,
                "notes": [(i * 480, 480, p, 96) for i, p in enumerate(MELODY_PITCHES)],
            },
            {
                "name": "Bass",
                "role": "bass",
                "program": 33,
                "notes": [(i * 1920, 1920, p, 80) for i, p in enumerate([50, 52, 54, 55])],
            },
            {
                "name": "Pad",
                "role": "harmony",
                "program": 0,
                "notes": [(i * 1920, 1920, 60 + (i * 5) % 8, 70) for i in range(4)],
            },
            {
                "name": "Drums",
                "role": "drums",
                "is_drum": True,
                "program": 0,
                "notes": [(i * 240, 120, 36, 96) for i in range(32)],
            },
        ],
    )


def test_remove_core_track_removes_melody_only():
    result = degrade_composition(_comp(), DegradationOp.REMOVE_CORE_TRACK)
    roles = [t.role for t in result.tracks]
    assert "melody" not in roles
    assert "bass" in roles and "harmony" in roles
    # 原曲目长度不变
    assert len(result.tracks) == 3


def test_stacked_severe_keeps_single_ops_order():
    comp = _comp()
    defaults = StyleDefaults()
    r_orig = evaluate_rules(comp, defaults)
    r_mild = evaluate_rules(degrade_stacked(comp, MILD_OPS), defaults)
    r_sev = evaluate_rules(degrade_stacked(comp, SEVERE_OPS), defaults)
    # 重度必须显著低于原始；轻度不升（允许并列）
    assert r_orig.R_rule >= r_mild.R_rule
    assert r_sev.R_rule < r_orig.R_rule


class TestSpearman:
    def test_perfect_monotonic(self):
        assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
        assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)

    def test_ties_average_ranks(self):
        rho = spearman([1, 1, 2], [1, 2, 3])
        assert 0 < rho < 1

    def test_degenerate_inputs(self):
        assert spearman([1, 1, 1], [1, 2, 3]) is None
        assert spearman([1, 2], [1, 2, 3]) is None
        assert spearman([1], [1]) is None
