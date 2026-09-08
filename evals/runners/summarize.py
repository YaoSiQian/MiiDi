"""按风格、样本类别与分数段汇总评测结果。

用法：
    python -m evals.runners.summarize --results evals/results

读取 results.csv，产出 evals/results/summary.md：
- 总体指标、分段分布
- 按风格 / 按类别分组均值
- 规则轴均值与反退化门击穿统计
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

AXES = ["harmony", "voice", "rhythm", "structure", "dynamics"]
GATES = ["gate_repetition", "gate_density", "gate_balance", "gate_spread"]
BUCKETS = [(80, 101, "80–100 优秀"), (60, 80, "60–79 合格"), (40, 60, "40–59 勉强"), (20, 40, "20–39 较差"), (0, 20, "0–19 不可用")]


def _mean(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows if r.get(key) not in ("", None)]
    return sum(vals) / len(vals) if vals else 0.0


def _group_table(title: str, groups: dict[str, list[dict]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| 分组 | 样本数 | 生成失败率 | composite 均值* | R_rule 均值* | J 均值* | 门击穿** |",
        "|------|--------|------------|-----------------|--------------|---------|----------|",
    ]
    for name in sorted(groups):
        rows = groups[name]
        ok = [r for r in rows if not r.get("error")]
        gated = sum(1 for r in ok if any(float(r.get(g) or 0) <= 0.05 for g in GATES))
        lines.append(
            f"| {name} | {len(rows)} | {len(rows) - len(ok)} | {_mean(ok, 'composite'):.1f} "
            f"| {_mean(ok, 'R_rule'):.1f} | {_mean(ok, 'J_mean'):.1f} | {gated} |"
        )
    lines.append("")
    lines.append("\\* 均值仅计入完成样本（生成失败样本的 0 分不摊入均值，失败单列）。")
    lines.append("\\* 门击穿：任一反退化门乘数 ≤ 0.05 的样本数（R_rule 被乘法门大幅压制）。")
    lines.append("")
    return lines


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def summarize(results_csv: Path) -> str:
    with open(results_csv, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("sample_id")]
    if not rows:
        return "no results"

    by_style: dict[str, list[dict]] = defaultdict(list)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_style[r["style"]].append(r)
        by_cat[r.get("category") or "basic"].append(r)

    failed = [r for r in rows if r.get("error")]
    scored = [r for r in rows if not r.get("error")]

    lines = [
        "# 评测结果汇总",
        "",
        f"- 样本总数：{len(rows)}（有效 {len(scored)}，生成/评分失败 {len(failed)}）",
        f"- composite 总均值：{_mean(scored, 'composite'):.1f}"
        f"（R_rule {_mean(scored, 'R_rule'):.1f}，Judge 均值 {_mean(scored, 'J_mean'):.1f}）",
        "",
        "## Composite 分段分布",
        "",
        "| 分段 | 样本数 |",
        "|------|--------|",
    ]
    for lo, hi, label in BUCKETS:
        n = sum(1 for r in scored if lo <= float(r["composite"]) < hi)
        lines.append(f"| {label} | {n} |")
    if len(scored) >= 3:
        rr = _pearson([float(r["R_rule"]) for r in scored], [float(r["J_mean"]) for r in scored])
        lines += [
            "",
            "## 主客观相关性",
            "",
            f"- Pearson r(R_rule, J_mean) = **{rr:.3f}**（n={len(scored)}）",
            "",
        ]
        n = sum(1 for r in scored if lo <= float(r["composite"]) < hi)
        lines.append(f"| {label} | {n} |")

    lines += ["", "## 规则轴均值（0–100）", "", "| 轴 | 均值 |", "|----|------|"]
    for ax in AXES:
        lines.append(f"| {ax} | {_mean(scored, ax):.1f} |")

    lines += ["", "## 反退化门均值（乘数 0–1）", "", "| 门 | 均值 | 最小值 |", "|----|------|--------|"]
    for g in GATES:
        vals = [float(r.get(g) or 0) for r in scored]
        lines.append(f"| {g.removeprefix('gate_')} | {sum(vals) / len(vals):.3f} | {min(vals):.3f} |")

    lines += _group_table("按风格分组", by_style)
    lines += _group_table("按样本类别分组", by_cat)

    if failed:
        lines += ["## 失败样本", "", "| 样本 | 错误 |", "|------|------|"]
        for r in failed:
            lines.append(f"| {r['sample_id']} | {r['error'][:80]} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    args = parser.parse_args()
    report = summarize(args.results / "results.csv")
    out = args.results / "summary.md"
    out.write_text(report)
    print(report)
    print(f"written to {out}")
