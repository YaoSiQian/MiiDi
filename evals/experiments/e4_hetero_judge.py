"""E4：异构 Judge 消自我偏好实验。

同一批样本分别用「生成同源 Judge」与「异构 Judge（另一免费档模型）」独立
评估 J1/J2/J3，报告两模型评分的 Pearson / Spearman 相关与均值差，回应
report.md §10 第一条局限（生成与评判同源）。

用法：
    python -m evals.experiments.e4_hetero_judge \
        --results evals/results --samples evals/samples \
        --model deepseek-v4-flash-free --limit 10

主 Judge 配置取自环境/.env；副 Judge 走 OpenCode Zen 免费档（--model 指定
型号）。产出 evals/results/e4_hetero_judge.json / .md；型号仅写入 JSON 冻结块，
markdown 以「Judge-A（同源）/ Judge-B（异构）」代称。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.experiments.e2_judge_consistency import (
    _load_env_dotenv,
    run_sample_rounds,
    select_samples,
)
from evals.experiments.stats import pearson, spearman
from miidi.eval.composite import compute_composite
from miidi.eval.score import evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack

ZEN_ENV = {"MODEL_NAME": ""}  # 置空 OPENAI_BASE_URL → 走 Zen 免费档路径


def run_hetero_judge(
    results_dir: Path,
    samples_dir: Path,
    model_b: str,
    limit: int,
    client_a: LLMClient | None = None,
) -> dict:
    picks = select_samples(results_dir, samples_dir)[:limit]
    if not picks:
        raise SystemExit("no usable sample dirs (composition.json + matching yaml required)")
    config_a = load_config()
    # 置空 OPENAI_BASE_URL → Zen 免费档路径，MODEL_NAME 用副 Judge 型号
    config_b = load_config({**ZEN_ENV, "MODEL_NAME": model_b})
    if client_a is None:
        client_a = LLMClient(config_a)
    client_b = LLMClient(config_b)

    records = []
    for i, (sid, d, sample) in enumerate(picks, 1):
        print(f"[{i}/{len(picks)}] {sid} ({sample.style})", flush=True)
        comp = Composition.model_validate(json.loads((d / "composition.json").read_text()))
        rule_report = evaluate_rules(comp, load_style_pack(sample.style).defaults)

        rounds_a = run_sample_rounds(comp, client_a, sample.style, sample.prompt, rule_report, 1)
        rounds_b = run_sample_rounds(comp, client_b, sample.style, sample.prompt, rule_report, 1)
        a, b = rounds_a[0], rounds_b[0]

        rec = {"sample_id": sid, "style": sample.style, "category": sample.sample_type}
        for name, r in (("judge_a", a), ("judge_b", b)):
            if "error" in r:
                rec[name] = {"error": r["error"]}
            else:
                rec[name] = {
                    "J1": r["J1"],
                    "J2": r["J2"],
                    "J3": r["J3"],
                    "composite": round(compute_composite(rule_report, _judge_stub(r)).composite, 2),
                }
        records.append(rec)
        print(
            f"    A: J={a.get('J1')}/{a.get('J2')}/{a.get('J3')} "
            f"B: J={b.get('J1')}/{b.get('J2')}/{b.get('J3')}",
            flush=True,
        )

    return {
        "freeze": {
            "judge_a": {
                "provider": config_a.provider,
                "base_url": config_a.base_url,
                "model": config_a.model,
            },
            "judge_b": {"provider": config_b.provider, "base_url": config_b.base_url, "model": model_b},
            "note": "型号仅记录于此 JSON（gitignored）；markdown 中以 Judge-A/Judge-B 代称",
        },
        "records": records,
        "summary": _summarize(records),
    }


class _judge_stub:
    """用单轮三分复刻 JudgeReport 以复用 compute_composite。"""

    def __init__(self, r: dict):
        self.J1, self.J2, self.J3 = r["J1"], r["J2"], r["J3"]


def _summarize(records: list[dict]) -> dict:
    dims = ("J1", "J2", "J3")
    ok = [r for r in records if "error" not in r["judge_a"] and "error" not in r["judge_b"]]
    summary = {"samples_ok": len(ok), "samples_total": len(records)}
    for dim in dims:
        xs = [r["judge_a"][dim] for r in ok]
        ys = [r["judge_b"][dim] for r in ok]
        summary[dim] = {
            "pearson": _round(pearson(xs, ys)),
            "spearman": _round(spearman(xs, ys)),
            "mean_a": _round(sum(xs) / len(xs)) if xs else None,
            "mean_b": _round(sum(ys) / len(ys)) if ys else None,
            "mean_diff": _round((sum(xs) - sum(ys)) / len(xs)) if xs else None,
        }
    ca = [r["judge_a"]["composite"] for r in ok]
    cb = [r["judge_b"]["composite"] for r in ok]
    summary["composite"] = {
        "pearson": _round(pearson(ca, cb)),
        "spearman": _round(spearman(ca, cb)),
    }
    return summary


def _round(v):
    return None if v is None else round(v, 3)


def to_markdown(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        "# E4 异构 Judge 消自我偏好实验",
        "",
        "## 方法",
        "",
        f"- {s['samples_total']} 个已完成评测样本（5 曲风 basic + constraint / hard / adversarial），"
        "冻结输入同 E2-Judge（SHA-256 见 JSON 冻结块）",
        "- 同一批作品分别由 Judge-A（生成同源模型）与 Judge-B（Zen 免费档异构模型，"
        "型号见 JSON 冻结块）独立评分 J1/J2/J3，规则轨共用同一份结果",
        "",
        "## 结果",
        "",
        "| 维度 | Pearson | Spearman | Judge-A 均值 | Judge-B 均值 | 均值差 (A−B) |",
        "|------|---------|----------|--------------|--------------|--------------|",
    ]
    for dim in ("J1", "J2", "J3"):
        d = s[dim]
        lines.append(
            f"| {dim} | {_f(d['pearson'])} | {_f(d['spearman'])} "
            f"| {_f(d['mean_a'])} | {_f(d['mean_b'])} | {_f(d['mean_diff'])} |"
        )
    c = s["composite"]
    lines.append(f"| composite | {_f(c['pearson'])} | {_f(c['spearman'])} | - | - | - |")
    lines += [
        "",
        "## 结论",
        "",
        (
            f"两评委在 composite 层面 Pearson={_f(c['pearson'])}、Spearman={_f(c['spearman'])}。"
            "相关越高，说明「生成与评判同源」带来的自我偏好偏置越可控；"
            "均值差列可直接读出评委间的宽严差异。"
            "若某维度相关偏低，应将该维度分数仅用于横向对比而非绝对结论。"
        ),
        "",
    ]
    return "\n".join(lines)


def _f(v):
    return "-" if v is None else f"{v:.3f}"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    _load_env_dotenv(repo_root)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    parser.add_argument("--samples", type=Path, default=Path("evals/samples"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--model", default="nemotron-3-ultra-free", help="Zen 免费档副 Judge 型号")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    out_dir = args.out or args.results

    payload = run_hetero_judge(args.results, args.samples, args.model, args.limit)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "e4_hetero_judge.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1)
    )
    md = to_markdown(payload)
    (out_dir / "e4_hetero_judge.md").write_text(md)
    print(md)
    print(f"written to {out_dir / 'e4_hetero_judge.md'}")


if __name__ == "__main__":
    main()
