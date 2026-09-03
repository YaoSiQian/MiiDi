from miidi.eval.composite import compute_composite
from miidi.eval.judge import JudgeReport
from miidi.eval.score import RuleReport


def test_composite_formula():
    rule = RuleReport(invalid=False, R_rule=80.0)
    judge = JudgeReport(J1=70.0, J2=90.0, J3=60.0)
    report = compute_composite(rule, judge)
    expected = 0.6 * 80.0 + 0.4 * ((70.0 + 90.0 + 60.0) / 3)
    assert abs(report.composite - expected) < 0.01
    assert report.R_rule == 80.0
    assert report.Judge_mean == (70.0 + 90.0 + 60.0) / 3


def test_composite_invalid_rule():
    rule = RuleReport(invalid=True, R_rule=0.0)
    judge = JudgeReport(J1=70.0, J2=90.0, J3=60.0)
    report = compute_composite(rule, judge)
    assert report.composite == 0.0
