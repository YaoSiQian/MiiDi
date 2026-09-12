"""把人工听感打分（human_ratings.jsonl）与机器分做相关分析。

用法：python -m evals.runners.human_correlation --results evals/results
读取 evals/results/human_ratings.jsonl（每行 {sample_id, score, annotator, timestamp}），
与 results.csv 中的 R_rule / J1 / J2 / J3 / J_mean / composite 做 Spearman 与 Pearson，
产出 evals/results/human_correlation.json / .md。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evals.experiments.stats import pearson, spearman


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    args = parser.parse_args()

    ratings = [
        json.loads(line)
        for line in (args.results / "human_ratings.jsonl").read_text().splitlines()
        if line.strip()
    ]
    machine = {}
    with open(args.results / "results.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            machine[r["sample_id"]] = r

    pairs = {k: ([], []) for k in ("R_rule", "J1", "J2", "J3", "J_mean", "composite")}
    table = []
    for rec in ratings:
        m = machine[rec["sample_id"]]
        table.append(
            {
                "sample_id": rec["sample_id"],
                "human": rec["score"],
                **{k: float(m[k]) for k in pairs},
            }
        )
        for k in pairs:
            pairs[k][0].append(float(m[k]))
            pairs[k][1].append(float(rec["score"]))

    summary = {"n": len(table), "dims": {}}
    for k, (xs, ys) in pairs.items():
        summary["dims"][k] = {
            "spearman": _r(spearman(xs, ys)),
            "pearson": _r(pearson(xs, ys)),
        }

    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / "human_correlation.json").write_text(
        json.dumps({"ratings": table, "summary": summary}, ensure_ascii=False, indent=1)
    )
    md = _markdown(table, summary)
    (args.results / "human_correlation.md").write_text(md)
    print(md)


def _r(v):
    return None if v is None else round(v, 3)


def _markdown(table, summary) -> str:
    lines = [
        "# 人工听感对照（单标注者初步实验）",
        "",
        f"n = {summary['n']}，四象限抽样（R_rule × J_mean 中位数分割）、覆盖 5 曲风；"
        "标注者仅凭整体听感打 1–5 分（不参照机器分）。",
        "局限：单标注者、未盲听（样本 id 可见）、分数范围受限（无 1–2 分档），"
        "与人类群体一致性未验证。",
        "",
        "| 样本 | 人工分 | composite | R_rule | J_mean |",
        "|------|--------|-----------|--------|--------|",
    ]
    for t in table:
        lines.append(
            f"| {t['sample_id']} | {t['human']} | {t['composite']:.1f} "
            f"| {t['R_rule']:.1f} | {t['J_mean']:.1f} |"
        )
    lines += [
        "",
        "## 相关（人工分 vs 机器分）",
        "",
        "| 维度 | Spearman | Pearson |",
        "|------|----------|---------|",
    ]
    for k, d in summary["dims"].items():
        lines.append(f"| {k} | {_f(d['spearman'])} | {_f(d['pearson'])} |")
    lines.append("")
    return "\n".join(lines)


def _f(v):
    return "-" if v is None else f"{v:.3f}"


if __name__ == "__main__":
    main()
