"""E1b：三档生成样本判别力实验（原始 / 轻度 / 重度退化）。

对每曲风取一个已完成评测的 basic 样本，构造三档退化：
- original：原始作品
- mild：单一轻度退化（起拍抖动）
- severe：叠加退化（音高随机化 + 起拍抖动 + 首小节复制 + 删除旋律核心轨）

每档分别做规则轨 + Judge 轨评分，报告 composite 层面的严格排序与
Spearman（退化档位 vs composite）；另附 remove_core_track 单独使用的
探针行（仅规则轨，零额外 Judge 调用），展示 G_balance 核心轨检查
对"删轨反升"盲区的修复闭环。

用法：
    python -m evals.experiments.e1b_tiers \
        --results evals/results --samples evals/samples

产出 evals/results/e1b_tiers.json / e1b_tiers.md。
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from evals.experiments.e1_discrimination import DegradationOp, degrade_composition
from evals.experiments.e2_judge_consistency import _load_env_dotenv, select_samples
from evals.experiments.stats import spearman
from miidi.eval.composite import compute_composite
from miidi.eval.judge import evaluate_judge
from miidi.eval.score import evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack

MILD_OPS = [DegradationOp.SCATTER_ONSET]
SEVERE_OPS = [
    DegradationOp.SCATTER_PITCH,
    DegradationOp.SCATTER_ONSET,
    DegradationOp.REPEAT_FIRST_BAR,
    DegradationOp.REMOVE_CORE_TRACK,
]


def degrade_stacked(comp: Composition, ops, seed: int = 42) -> Composition:
    cur = comp
    for i, op in enumerate(ops):
        cur = degrade_composition(cur, op, seed=seed + i)
    return cur


def run_tiers(
    results_dir: Path,
    samples_dir: Path,
    per_style: int = 1,
    client: LLMClient | None = None,
) -> dict:
    picks = select_samples(results_dir, samples_dir, per_style=per_style, categories=())
    if not picks:
        raise SystemExit("no usable sample dirs (composition.json + matching yaml required)")
    config = load_config()
    if client is None:
        client = LLMClient(config)

    records = []
    for i, (sid, d, sample) in enumerate(picks, 1):
        print(f"[{i}/{len(picks)}] {sid} ({sample.style})", flush=True)
        comp = Composition.model_validate(json.loads((d / "composition.json").read_text()))
        defaults = load_style_pack(sample.style).defaults
        tiers = {
            "original": comp,
            "mild": degrade_stacked(comp, MILD_OPS),
            "severe": degrade_stacked(comp, SEVERE_OPS),
        }
        tier_out = {}
        for name, tier_comp in tiers.items():
            rr = evaluate_rules(tier_comp, defaults)
            print(f"    {name}: R_rule={rr.R_rule:.2f} G_balance={rr.gates['balance']:.3f}", flush=True)
            jr = evaluate_judge(tier_comp, rr, client, sample.style, sample.prompt)
            tier_out[name] = {
                "R_rule": round(rr.R_rule, 2),
                "J1": jr.J1,
                "J2": jr.J2,
                "J3": jr.J3,
                "composite": round(compute_composite(rr, jr).composite, 2),
                "gate_balance": round(rr.gates["balance"], 3),
            }
        # 探针：仅删旋律核心轨（规则轨，无 Judge 调用）
        probe_rule = evaluate_rules(degrade_composition(comp, DegradationOp.REMOVE_CORE_TRACK), defaults)
        probe_delta = probe_rule.R_rule - tier_out["original"]["R_rule"]
        print(
            f"    probe remove_core_track: R_rule={probe_rule.R_rule:.2f} "
            f"(delta {probe_delta:+.2f}) G_balance={probe_rule.gates['balance']:.3f}",
            flush=True,
        )
        records.append(
            {
                "sample_id": sid,
                "style": sample.style,
                "tiers": tier_out,
                "probe_remove_core_track": {
                    "R_rule": round(probe_rule.R_rule, 2),
                    "R_rule_delta_vs_original": round(probe_delta, 2),
                    "gate_balance": round(probe_rule.gates["balance"], 3),
                },
            }
        )

    payload = {
        "freeze": {
            "provider": config.provider,
            "base_url": config.base_url,
            "model": config.model,
            "mild_ops": [op.value for op in MILD_OPS],
            "severe_ops": [op.value for op in SEVERE_OPS],
            "note": "模型型号仅记录于此 JSON（gitignored）",
        },
        "records": records,
        "summary": _summarize(records),
    }
    return payload


def _summarize(records: list[dict]) -> dict:
    strict = partial = violated = 0
    composites: list[float] = []
    tier_ranks: list[int] = []
    probe_deltas = []
    for rec in records:
        t = rec["tiers"]
        c_orig, c_mild, c_sev = t["original"]["composite"], t["mild"]["composite"], t["severe"]["composite"]
        if c_orig > c_mild > c_sev:
            strict += 1
        elif c_orig >= c_mild >= c_sev:
            partial += 1
        else:
            violated += 1
        composites += [c_orig, c_mild, c_sev]
        tier_ranks += [0, 1, 2]
        probe_deltas.append(rec["probe_remove_core_track"]["R_rule_delta_vs_original"])

    rho = spearman(tier_ranks, composites)
    summary = {
        "samples": len(records),
        "strict_ordering": strict,
        "weak_ordering_incl_ties": partial,
        "ordering_violated": violated,
        "spearman_tier_vs_composite": round(rho, 3) if rho is not None else None,
        "probe_remove_core_track_mean_delta": round(statistics.mean(probe_deltas), 2),
        "probe_all_detected": all(d <= 0 for d in probe_deltas),
    }
    return summary


def to_markdown(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        "# E1b 三档生成样本判别力实验",
        "",
        "## 方法",
        "",
        "- 每曲风取 1 个已完成评测的 basic 样本（共 5 个），构造原始 / 轻度 / 重度三档："
        "轻度=起拍抖动（单一操作）；重度=音高随机化+起拍抖动+首小节复制+删旋律核心轨（叠加）",
        "- 每档均做规则轨 + Judge 轨评分（Judge 与生成同源，见 e1b_tiers.json 冻结块），"
        "考察 composite 层面的档位排序",
        "- 探针行：只删旋律核心轨、只评规则轨——对应 E1 发现的「删轨反升」盲区与 "
        "G_balance 核心轨检查的修复闭环",
        "",
        "## 逐样本结果",
        "",
        "| 样本 | 档位 | R_rule | G_balance | J1 | J2 | J3 | composite |",
        "|------|------|--------|-----------|----|----|----|-----------|",
    ]
    for rec in payload["records"]:
        for tier in ("original", "mild", "severe"):
            t = rec["tiers"][tier]
            lines.append(
                f"| {rec['sample_id']} | {tier} | {t['R_rule']:.2f} | {t['gate_balance']:.3f} "
                f"| {t['J1']:.1f} | {t['J2']:.1f} | {t['J3']:.1f} | {t['composite']:.2f} |"
            )
        p = rec["probe_remove_core_track"]
        lines.append(
            f"| {rec['sample_id']} | 探针：仅删旋律轨 | {p['R_rule']:.2f} "
            f"| {p['gate_balance']:.3f} | - | - | - | （ΔR_rule {p['R_rule_delta_vs_original']:+.2f}） |"
        )

    lines += [
        "",
        "## 汇总",
        "",
        f"- composite 严格排序（original > mild > severe）："
        f"{s['strict_ordering']}/{s['samples']} 个样本；含并列弱排序 "
        f"{s['weak_ordering_incl_ties']}/{s['samples']}；违反排序 {s['ordering_violated']} 个",
        f"- 档位 vs composite 的 Spearman ρ = {s['spearman_tier_vs_composite']}",
        f"- 删旋律轨探针：平均 ΔR_rule = {s['probe_remove_core_track_mean_delta']:+.2f}，"
        f"全部检出（Δ≤0）：{'是' if s['probe_all_detected'] else '否'}"
        "（旧评估器下该操作曾反升 +1.7，见 §5 E1/E3）",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    _load_env_dotenv(repo_root)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    parser.add_argument("--samples", type=Path, default=Path("evals/samples"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out or args.results

    payload = run_tiers(args.results, args.samples)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "e1b_tiers.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    md = to_markdown(payload)
    (out_dir / "e1b_tiers.md").write_text(md)
    print(md)
    print(f"written to {out_dir / 'e1b_tiers.md'}")


if __name__ == "__main__":
    main()
