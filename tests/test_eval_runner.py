from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from evals.runners.run_eval import EvalResult, run_single_sample


def test_eval_result_to_dict():
    result = EvalResult(
        sample_id="pop_basic_01",
        style="pop",
        R_rule=75.0,
        J1=80.0,
        J2=85.0,
        J3=70.0,
        composite=76.0,
        note_count=120,
        track_count=4,
        duration_bars=32,
    )
    d = result.to_dict()
    assert d["sample_id"] == "pop_basic_01"
    assert d["composite"] == 76.0
    assert d["R_rule"] == 75.0
    assert d["note_count"] == 120
    assert d["error"] == ""


def test_eval_result_error_field():
    result = EvalResult(
        sample_id="test_01",
        style="pop",
        error="generation failed",
    )
    d = result.to_dict()
    assert d["error"] == "generation failed"
    assert d["composite"] == 0.0


def test_run_single_sample_generation_failure():
    from evals.samples.schema import EvalSample

    sample = EvalSample(
        id="pop_basic_01",
        style="pop",
        prompt="Write a happy pop song",
    )
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.comp = None

    with patch("evals.runners.run_eval.run_pipeline", return_value=mock_result):
        result = run_single_sample(sample, mock_client, Path("/tmp/test_out"))
        assert result.error == "generation failed"
        assert result.composite == 0.0


def test_run_single_sample_exception_handling():
    from evals.samples.schema import EvalSample

    sample = EvalSample(
        id="pop_basic_01",
        style="pop",
        prompt="Write a happy pop song",
    )
    mock_client = MagicMock()

    with patch("evals.runners.run_eval.run_pipeline", side_effect=RuntimeError("LLM timeout")):
        result = run_single_sample(sample, mock_client, Path("/tmp/test_out"))
        assert "LLM timeout" in result.error
        assert result.composite == 0.0


def test_run_single_sample_invalid_composition():
    from evals.samples.schema import EvalSample
    from miidi.eval.score import RuleReport

    sample = EvalSample(
        id="pop_basic_01",
        style="pop",
        prompt="Write a happy pop song",
    )
    mock_client = MagicMock()

    mock_comp = MagicMock()
    mock_comp.tracks = []
    mock_comp.total_bars.return_value = 32.0

    mock_pipeline_result = MagicMock()
    mock_pipeline_result.comp = mock_comp

    invalid_report = RuleReport(invalid=True, R_rule=0.0, violations=())

    with patch("evals.runners.run_eval.run_pipeline", return_value=mock_pipeline_result), \
         patch("evals.runners.run_eval.load_style_pack") as mock_load, \
         patch("evals.runners.run_eval.evaluate_rules", return_value=invalid_report):
        mock_pack = MagicMock()
        mock_pack.defaults = MagicMock()
        mock_load.return_value = mock_pack
        result = run_single_sample(sample, mock_client, Path("/tmp/test_out"))
        assert result.error == "invalid composition"
        assert result.composite == 0.0
        assert result.R_rule == 0.0


def test_run_eval_creates_output_files(tmp_path):
    from evals.samples.schema import EvalSample

    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    sample_data = {
        "id": "pop_basic_01",
        "style": "pop",
        "prompt": "Write a happy pop song",
    }
    (samples_dir / "pop_basic_01.yaml").write_text(yaml.dump(sample_data))

    out_dir = tmp_path / "results"
    mock_client = MagicMock()

    mock_comp = MagicMock()
    mock_comp.tracks = []
    mock_comp.total_bars.return_value = 16.0

    mock_pipeline_result = MagicMock()
    mock_pipeline_result.comp = mock_comp

    mock_rule_report = MagicMock()
    mock_rule_report.R_rule = 70.0
    mock_rule_report.invalid = False

    mock_judge_report = MagicMock()
    mock_judge_report.J1 = 80.0
    mock_judge_report.J2 = 75.0
    mock_judge_report.J3 = 85.0

    mock_composite = MagicMock()
    mock_composite.composite = 76.0

    with patch("evals.runners.run_eval.run_pipeline", return_value=mock_pipeline_result), \
         patch("evals.runners.run_eval.load_style_pack") as mock_load, \
         patch("evals.runners.run_eval.evaluate_rules", return_value=mock_rule_report), \
         patch("evals.runners.run_eval.evaluate_judge", return_value=mock_judge_report), \
         patch("evals.runners.run_eval.compute_composite", return_value=mock_composite):
        mock_pack = MagicMock()
        mock_pack.defaults = MagicMock()
        mock_load.return_value = mock_pack

        from evals.runners.run_eval import run_eval
        results = run_eval(samples_dir, out_dir, client=mock_client)

    assert len(results) == 1
    assert results[0].sample_id == "pop_basic_01"
    assert results[0].composite == 76.0

    csv_path = out_dir / "results.csv"
    md_path = out_dir / "results.md"
    assert csv_path.exists()
    assert md_path.exists()

    csv_content = csv_path.read_text()
    assert "pop_basic_01" in csv_content
    assert "sample_id" in csv_content

    md_content = md_path.read_text()
    assert "Evaluation Results" in md_content
    assert "pop_basic_01" in md_content
