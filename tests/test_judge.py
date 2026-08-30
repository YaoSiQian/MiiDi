import pytest
from unittest.mock import MagicMock
from miidi.eval.judge import JudgeReport, evaluate_judge
from miidi.eval.score import RuleReport
from miidi.schema.model import Composition, Section, Track

def _make_comp():
    return Composition(
        meta={"title": "test", "bpm": 120, "time_signature": [4, 4],
              "key": {"tonic_pc": 0, "mode": "major"}},
        structure=[Section(name="verse", start_bar=0, bars=4)],
        harmony=[{"bar": 0, "dur_bars": 4.0, "symbol": "C"}],
        tracks=[Track(name="Lead", program=73, role="melody",
                      notes=[(0, 480, 60, 96), (480, 480, 64, 96)])],
    )

def test_judge_report_structure():
    report = JudgeReport(J1=80.0, J2=90.0, J3=70.0,
                         per_item={"J1": [], "J2": [], "J3": []},
                         evidence=[])
    d = report.to_dict()
    assert d["J1"] == 80.0
    assert d["J2"] == 90.0
    assert d["J3"] == 70.0
    assert "composite" not in d

def test_evaluate_judge_returns_report():
    client = MagicMock()
    client.respond_json.return_value = {
        "score": 75.0,
        "per_item": [{"item": "scale_adherence", "verdict": "yes", "evidence": "all notes in C major"}],
        "evidence": [{"track": "Lead", "bar": 0, "text": "scale adherence verified"}],
    }
    comp = _make_comp()
    rule_report = RuleReport(invalid=False, R_rule=65.0)
    report = evaluate_judge(comp, rule_report, client, "pop",
                            prompt="Write a catchy pop verse with piano and drums at 120 BPM.")
    assert isinstance(report, JudgeReport)
    assert 0 <= report.J1 <= 100
    assert 0 <= report.J2 <= 100
    assert 0 <= report.J3 <= 100