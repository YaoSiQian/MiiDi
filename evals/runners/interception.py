"""results.csv 拦截层标签列：A1 格式门 / 乘法门 / 轴扣分 / 无拦截。

对应 report.md §9(3)「防御分层」——读分数必须附带"哪一层拦的"标签。
"""

from __future__ import annotations

from miidi.eval.score import RuleReport

GATE_THRESHOLD = 0.999


def classify_interception(rule_report: RuleReport) -> str:
    """按三层防御给出单标签；多重乘法门并列时用 + 连接。"""
    if rule_report.invalid:
        return "A1_format"
    fired = [f"G_{n}" for n, v in rule_report.gates.items() if v < GATE_THRESHOLD]
    if fired:
        return "+".join(fired)
    if rule_report.R_rule < 99.999:
        return "axis_deduction"
    return "none"
