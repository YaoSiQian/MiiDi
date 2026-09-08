"""E1/E2/E3 有效性验证入口：对一个已生成的 Composition 跑规则轨验证实验。

用法（composition 通常来自评测产出的 composition.json）：
    python -m evals.experiments.run_experiments \
        --composition evals/results/base_composition.json \
        --style pop --out evals/results

产出 evals/results/experiments.md：
- E1 区分度：四种退化操作是否让目标轴按预期下降
- E2 确定性：规则轨三次评估是否完全一致
- E3 对抗性：所有退化版本的 R_rule 是否都不高于原版
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.experiments.e1_discrimination import (
    ATTRIBUTION_TARGETS,
    DegradationOp,
    check_attribution,
    degrade_composition,
)
from evals.experiments.e2_consistency import check_rule_determinism
from evals.experiments.e3_adversarial import run_adversarial
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack

OP_LABELS = {
    DegradationOp.SCATTER_PITCH: "scatter_pitch（音高随机化）",
    DegradationOp.REMOVE_TRACK: "remove_track（删除末轨）",
    DegradationOp.SCATTER_ONSET: "scatter_onset（起拍抖动 ±60 tick）",
    DegradationOp.REPEAT_FIRST_BAR: "repeat_first_bar（首小节复制全曲）",
}


def run_all(comp: Composition, style: str) -> str:
    defaults = load_style_pack(style).defaults
    lines = [
        "# 有效性验证实验（E1 / E2 / E3）",
        "",
        f"- 基准作品：{style} 风格 `Composition`，"
        f"{sum(len(t.notes) for t in comp.tracks)} 个音符 / {len(comp.tracks)} 轨 / "
        f"{int(comp.total_bars())} 小节",
        "- 规则轨为纯确定性代码（不含 LLM），实验可完全复现",
        "",
        "## E1 区分度实验",
        "",
        "对基准作品施加四种退化操作，检查目标轴分数是否按预期下降"
        "（门槛值见 `ATTRIBUTION_TARGETS`）：",
        "",
        "| 退化操作 | 目标轴 | 实际降幅（正值=分数下降） | 判定 |",
        "|----------|--------|----------|------|",
    ]
    e1_results = []
    for op in DegradationOp:
        degraded = degrade_composition(comp, op)
        r = check_attribution(comp, degraded, op, defaults)
        e1_results.append(r)
        for axis_name, min_drop in ATTRIBUTION_TARGETS[op]:
            drop = r.axis_drops.get(axis_name)
            if drop is None:
                lines.append(f"| {OP_LABELS[op]} | {axis_name} | n/a | ✗ |")
            else:
                mark = "✓" if drop >= min_drop else "✗"
                lines.append(
                    f"| {OP_LABELS[op]} | {axis_name} "
                    f"| {drop:+.3f}（门槛 ≥{min_drop:.2f}） | {mark} |"
                )
    e1_pass = all(r.passed for r in e1_results)
    lines += ["", f"**E1 结论**：{'全部通过 —— 规则轨对四类退化均有预期区分度' if e1_pass else '存在未达标项，评分器对某类退化不敏感'}。", ""]

    e2 = check_rule_determinism(comp, defaults, runs=3)
    lines += [
        "## E2 一致性实验",
        "",
        "同一 Composition 独立评估 3 次，验证规则轨确定性：",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| R_rule 三次取值 | [{e2.rule_range['min']:.4f}, {e2.rule_range['max']:.4f}] |",
        f"| 极差（range） | {e2.rule_range['range']:.6f} |",
        f"| 标准差 | {e2.rule_range['std']:.6f} |",
        f"| 判定 | {'✓ 完全确定，range = 0' if e2.rule_deterministic else '✗ 存在波动'} |",
        "",
    ]

    e3 = run_adversarial(comp, defaults)
    lines += [
        "## E3 对抗实验",
        "",
        f"基准 R_rule = {e3.original_score:.2f}。四种退化版本的得分：",
        "",
        "| 退化操作 | R_rule | 相对基准 |",
        "|----------|--------|----------|",
    ]
    for op in DegradationOp:
        v = e3.degraded_scores[op.value]
        lines.append(f"| {OP_LABELS[op]} | {v:.2f} | {v - e3.original_score:+.2f} |")
    lines += [
        "",
        "**E3 结论**："
        + ("✓ 全部退化版本得分不高于基准，无明显作弊空间" if e3.all_detected else "✗ 存在退化后得分反升的漏洞"),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--composition", type=Path, required=True, help="基准作品 JSON 路径")
    parser.add_argument("--style", required=True, help="风格包名（用于密度等风格参考值）")
    parser.add_argument("--out", type=Path, required=True, help="实验报告输出目录")
    args = parser.parse_args()

    comp = Composition.model_validate(json.loads(args.composition.read_text()))
    report = run_all(comp, args.style)

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "experiments.md"
    out_path.write_text(report)
    print(report)
    print(f"written to {out_path}")


if __name__ == "__main__":
    main()
