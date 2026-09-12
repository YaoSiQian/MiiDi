from __future__ import annotations

import pytest

from evals.experiments.e2_judge_consistency import (
    _j3_band,
    quadratic_weighted_kappa,
    select_samples,
    verdict_agreement,
)


def _items(*verdicts: str) -> list[dict]:
    return [{"item": f"item {i}", "verdict": v} for i, v in enumerate(verdicts)]


class TestVerdictAgreement:
    def test_perfect_agreement(self):
        rounds = [_items("yes", "no", "partial")] * 3
        rate, n, full = verdict_agreement(rounds)
        assert rate == 1.0
        assert n == 3
        assert full

    def test_full_disagreement(self):
        rounds = [_items("yes", "yes"), _items("no", "no"), _items("partial", "partial")]
        rate, n, _full = verdict_agreement(rounds)
        assert rate == 0.0
        assert n == 2

    def test_length_mismatch_truncates_and_flags(self):
        rounds = [_items("yes", "yes", "no"), _items("yes", "yes")]
        rate, n, full = verdict_agreement(rounds)
        assert rate == 1.0
        assert n == 2
        assert not full

    def test_empty_items(self):
        rate, n, full = verdict_agreement([[], []])
        assert rate is None
        assert n == 0
        assert not full


class TestQuadraticWeightedKappa:
    def test_too_few_pairs(self):
        assert quadratic_weighted_kappa([(1, 2)]) is None

    def test_perfect_agreement(self):
        pairs = [(1, 1), (2, 2), (3, 3), (1, 1), (2, 2)]
        assert quadratic_weighted_kappa(pairs) == pytest.approx(1.0)

    def test_constant_labels_degenerate(self):
        # 全部落在同一档：期望分母退化为 0，约定返回 None
        assert quadratic_weighted_kappa([(2, 2), (2, 2), (2, 2)]) is None

    def test_out_of_band_pair(self):
        assert quadratic_weighted_kappa([(1, 9), (2, 2)]) is None

    def test_near_agreement_beats_far(self):
        near = quadratic_weighted_kappa([(2, 3), (3, 2), (1, 2), (2, 1), (3, 3)])
        far = quadratic_weighted_kappa([(0, 4), (4, 0), (1, 3), (3, 1), (2, 2)])
        assert near > 0
        assert far < 0
        assert near > far


class TestJ3Band:
    def test_parse(self):
        assert _j3_band("3") == 3
        assert _j3_band(4) == 4
        assert _j3_band("6") is None
        assert _j3_band("n/a") is None
        assert _j3_band(None) is None


class TestSelectSamples:
    def test_selection_covers_styles_and_categories(self, tmp_path):
        results = tmp_path / "results"
        samples = tmp_path / "samples"
        samples.mkdir()
        plan = {
            "classical_basic_01": "classical",
            "classical_basic_02": "classical",
            "lofi_basic_01": "lofi",
            "rerun_pop_basic_02": "pop",
            "constraint_01": "jazz",
            "hard_01": "hard",
            "adversarial_01": "adversarial",
        }
        for sid, style in plan.items():
            d = results / sid
            d.mkdir(parents=True)
            (d / "composition.json").write_text("{}")
            clean = sid.removeprefix("rerun_")
            samples.joinpath(f"{clean}.yaml").write_text(
                f"id: {clean}\nstyle: {style}\nprompt: p\n"
            )
        # 无 composition.json 的目录与缺 yaml 的样本都应被跳过
        (results / "broken").mkdir()
        (results / "orphan_01").mkdir()
        (results / "orphan_01" / "composition.json").write_text("{}")

        picks = select_samples(results, samples)

        ids = [sid for sid, _d, _s in picks]
        # 每风格 1 个 basic（字典序第一，rerun_ 前缀被剥掉后仍可匹配 yaml）
        assert "classical_basic_01" in ids
        assert "classical_basic_02" not in ids
        assert "lofi_basic_01" in ids
        assert "pop_basic_02" in ids
        # 三个类别各 1 个
        assert "constraint_01" in ids
        assert "hard_01" in ids
        assert "adversarial_01" in ids
        assert len(ids) == 6
        rec = dict((sid, s) for sid, _d, s in picks)
        assert rec["pop_basic_02"].style == "pop"
        assert rec["pop_basic_02"].sample_type == "basic"
