"""重跑首轮生成失败的样本，捕获 stage_log 与错误原因，产出 rerun_failed.md。

主结果表保持首轮原样（避免幸存者偏差）；本脚本的重测数据用于归因分析：
- 重测成功 → 首轮失败为瞬时故障（端点抖动）
- 重测仍失败 → stage_log 定位到具体阶段，属持续失败模式

用法：
    python -m evals.runners.rerun_failed --ids pop_basic_01,pop_basic_02 \
        --samples evals/samples --out evals/results
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from miidi.eval.composite import compute_composite
from miidi.eval.judge import evaluate_judge
from miidi.eval.score import evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.pipeline.orchestrator import run_pipeline
from miidi.skills.loader import load_style_pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", required=True, help="逗号分隔的样本 id")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    catalog: dict[str, dict] = {}
    for f in sorted(args.samples.glob("*.yaml")):
        data = yaml.safe_load(f.read_text()) or {}
        if data.get("id"):
            catalog[data["id"]] = data

    def run(sid: str) -> dict:
        sample = catalog[sid]
        rec = {"sample_id": sid, "style": sample["style"], "outcome": "", "detail": "",
               "R_rule": 0.0, "J_mean": 0.0, "composite": 0.0, "notes": 0}
        pack = load_style_pack(sample["style"])
        result = run_pipeline(
            sample["prompt"], sample["style"], client, out_dir=args.out / f"rerun_{sid}", store=None
        )
        if result.comp is None:
            rec["outcome"] = "failed again"
            rec["detail"] = " | ".join(result.stage_log[-3:])[:200]
            return rec
        rec["notes"] = sum(len(t.notes) for t in result.comp.tracks)
        rule = evaluate_rules(result.comp, pack.defaults)
        rec["R_rule"] = round(rule.R_rule, 1)
        if rule.invalid:
            rec["outcome"] = "invalid composition"
            rec["detail"] = "; ".join(v.message for v in rule.violations[:3])[:200]
            return rec
        judge = evaluate_judge(result.comp, rule, client, sample["style"], sample["prompt"])
        comp_report = compute_composite(rule, judge)
        rec["outcome"] = "recovered"
        rec["J_mean"] = round(comp_report.Judge_mean, 1)
        rec["composite"] = round(comp_report.composite, 1)
        return rec

    client = LLMClient(load_config())
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, sid): sid for sid in args.ids.split(",") if sid in catalog}
        for fut in as_completed(futures):
            rec = fut.result()
            print(f"[{futures[fut]}] {rec['outcome']}: {rec['detail'] or rec['composite']}")
            records.append(rec)
    client.close()

    lines = [
        "# 首轮失败样本重测",
        "",
        "首轮（主结果表）保持原样计入；本表用于失败归因：`recovered` = 瞬时故障，"
        "`failed again / invalid` = 持续失败模式（detail 为阶段日志/违规摘要）。",
        "",
        "| 样本 | 风格 | 重测结果 | R_rule | J 均值 | composite | 音符数 | detail |",
        "|------|------|----------|--------|--------|-----------|--------|--------|",
    ]
    for r in sorted(records, key=lambda x: x["sample_id"]):
        lines.append(
            f"| {r['sample_id']} | {r['style']} | {r['outcome']} | {r['R_rule']} "
            f"| {r['J_mean']} | {r['composite']} | {r['notes']} | {r['detail'][:80]} |"
        )
    recovered = sum(1 for r in records if r["outcome"] == "recovered")
    lines += [
        "",
        f"**重测结论**：{recovered}/{len(records)} 重测成功（瞬时故障率 "
        f"{(len(records) - recovered)}/{len(records)} 为持续失败）。",
        "",
    ]
    out_path = args.out / "rerun_failed.md"
    out_path.write_text("\n".join(lines))
    print(f"written to {out_path}")


if __name__ == "__main__":
    main()
