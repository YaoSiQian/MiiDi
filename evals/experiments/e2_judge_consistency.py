"""E2-Judge：LLM 评委轨重复一致性实验。

对已完成评测的 composition.json 冻结输入（文件 SHA-256 写入 JSON 冻结块），
每个样本独立重复 N 轮 J1/J2/J3 评分（温度 0.0，与主评测一致），报告：
- J1/J2/J3 每维均值 ± 标准差与极差
- J1 风格清单逐项 verdict 一致率、J2 约束判定一致率（按输出位置对齐）
- J3 档位（1-5）严格一致率、±1 档一致率与合并成对比较的二次加权 κ
- composite 极差（R_rule 确定性，波动全部来自 Judge 轨）

用法：
    python -m evals.experiments.e2_judge_consistency \
        --results evals/results --samples evals/samples --rounds 3

产出 evals/results/judge_consistency.json（含冻结块与逐轮原始分）与
judge_consistency.md（人读报告）。模型型号仅记录在 JSON 冻结块中。
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import statistics
from pathlib import Path

import yaml

from evals.schema import EvalSample
from miidi.eval.composite import compute_composite
from miidi.eval.judge import evaluate_judge
from miidi.eval.score import evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack

J3_BANDS = 5


def _load_env_dotenv(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _iter_sample_dirs(results_dir: Path) -> list[tuple[str, Path]]:
    """(去 rerun_ 前缀的 sample_id, 目录)，只收含 composition.json 的目录。"""
    out = []
    for d in sorted(results_dir.iterdir()):
        if d.is_dir() and (d / "composition.json").exists():
            out.append((d.name.removeprefix("rerun_"), d))
    return out


def select_samples(
    results_dir: Path,
    samples_dir: Path,
    per_style: int = 1,
    categories: tuple[str, ...] = ("constraint", "hard", "adversarial"),
) -> list[tuple[str, Path, EvalSample]]:
    """每曲风取字典序第一的 basic 样本，再加每个类别字典序第一的样本。"""
    loaded = []
    for sid, d in _iter_sample_dirs(results_dir):
        yml = samples_dir / f"{sid}.yaml"
        if not yml.exists():
            continue
        with open(yml) as fh:
            loaded.append((sid, d, EvalSample(**yaml.safe_load(fh))))

    picks: dict[str, tuple[str, Path, EvalSample]] = {}
    basics_by_style: dict[str, list[tuple[str, Path, EvalSample]]] = {}
    for sid, d, s in loaded:
        if s.sample_type == "basic":
            basics_by_style.setdefault(s.style, []).append((sid, d, s))
        elif s.sample_type in categories and s.sample_type not in picks:
            picks[s.sample_type] = (sid, d, s)
    for style in sorted(basics_by_style):
        for sid, d, s in sorted(basics_by_style[style])[:per_style]:
            picks[f"basic:{style}"] = (sid, d, s)
    return [picks[k] for k in sorted(picks)]


def verdict_agreement(round_items: list[list[dict]]) -> tuple[float | None, int, bool]:
    """按输出位置对齐各轮 per_item，返回(一致率, 对齐项数, 轮间项数完全相等)。

    LLM 输出的清单长度轮间可能不一致；此时只对齐到最短长度并把
    "长度是否完全相等"交给调用方如实披露。
    """
    counts = [len(items) for items in round_items]
    n_align = min(counts) if counts else 0
    if n_align == 0:
        return None, 0, False
    aligned = [items[:n_align] for items in round_items]
    same = sum(
        1 for i in range(n_align) if len({r[i].get("verdict", "") for r in aligned}) == 1
    )
    return same / n_align, n_align, len(set(counts)) == 1


def quadratic_weighted_kappa(pairs: list[tuple[int, int]], k: int = J3_BANDS) -> float | None:
    """合并全部成对比较后的二次加权 κ；退化分布（常值序列）返回 None。"""
    if len(pairs) < 2:
        return None
    n = len(pairs)
    obs = [[0.0] * k for _ in range(k)]
    for a, b in pairs:
        if not (0 <= a < k and 0 <= b < k):
            return None
        obs[a][b] += 1
    row_marg = [sum(obs[i]) for i in range(k)]
    col_marg = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w_max = (k - 1) ** 2
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / w_max
            num += w * obs[i][j] / n
            den += w * row_marg[i] * col_marg[j] / (n * n)
    if den == 0:
        return None
    return 1.0 - num / den


def _dim_stats(scores: list[float]) -> dict:
    return {
        "mean": round(statistics.mean(scores), 2),
        "std": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0,
        "range": round(max(scores) - min(scores), 2),
    }


def _j3_band(verdict: object) -> int | None:
    try:
        band = int(str(verdict).strip())
    except (TypeError, ValueError):
        return None
    return band if 1 <= band <= J3_BANDS else None


def run_sample_rounds(
    comp: Composition,
    client: LLMClient,
    style: str,
    prompt: str,
    rule_report,
    rounds: int,
) -> list[dict]:
    rounds_out = []
    for r in range(1, rounds + 1):
        try:
            jr = evaluate_judge(comp, rule_report, client, style, prompt)
            entry = {
                "round": r,
                "J1": jr.J1,
                "J2": jr.J2,
                "J3": jr.J3,
                "composite": round(compute_composite(rule_report, jr).composite, 2),
                "per_item": jr.per_item,
            }
        except Exception as exc:
            entry = {"round": r, "error": str(exc)[:200]}
        rounds_out.append(entry)
        if "error" in entry:
            print(f"    round {r}: ERROR {entry['error'][:120]}", flush=True)
        else:
            print(
                f"    round {r}: J1={entry['J1']} J2={entry['J2']} J3={entry['J3']}",
                flush=True,
            )
    return rounds_out


def run_judge_consistency(
    results_dir: Path,
    samples_dir: Path,
    rounds: int = 3,
    per_style: int = 1,
    client: LLMClient | None = None,
) -> dict:
    picks = select_samples(results_dir, samples_dir, per_style=per_style)
    if not picks:
        raise SystemExit("no usable sample dirs (composition.json + matching yaml required)")
    config = load_config()
    if client is None:
        client = LLMClient(config)

    records = []
    for i, (sid, d, sample) in enumerate(picks, 1):
        print(f"[{i}/{len(picks)}] {sid} ({sample.style}, {sample.sample_type})", flush=True)
        comp = Composition.model_validate(json.loads((d / "composition.json").read_text()))
        rule_report = evaluate_rules(comp, load_style_pack(sample.style).defaults)
        rounds_out = run_sample_rounds(
            comp, client, sample.style, sample.prompt, rule_report, rounds
        )
        records.append(
            {
                "sample_id": sid,
                "style": sample.style,
                "category": sample.sample_type,
                "composition_sha256": hashlib.sha256(
                    (d / "composition.json").read_bytes()
                ).hexdigest(),
                "prompt_sha256": hashlib.sha256(sample.prompt.encode()).hexdigest(),
                "rounds": rounds_out,
            }
        )

    payload = {
        "freeze": {
            "provider": config.provider,
            "base_url": config.base_url,
            "model": config.model,
            "temperature": 0.0,
            "rounds": rounds,
            "note": "同一输入冻结后独立重复评分；模型型号仅记录于此 JSON（gitignored）",
        },
        "records": records,
    }
    payload["summary"] = _summarize(records)
    return payload


def _summarize(records: list[dict]) -> dict:
    dims = ("J1", "J2", "J3")
    per_sample = []
    pooled_j3_pairs: list[tuple[int, int]] = []
    j1_agreements, j2_agreements = [], []
    for rec in records:
        ok = [r for r in rec["rounds"] if "error" not in r]
        row: dict = {"sample_id": rec["sample_id"], "rounds_ok": len(ok)}
        if len(ok) >= 2:
            for dim in dims:
                row[dim] = _dim_stats([r[dim] for r in ok])
            row["composite_range"] = round(
                max(r["composite"] for r in ok) - min(r["composite"] for r in ok), 2
            )
            j1_ag, _, j1_full = verdict_agreement([r["per_item"].get("J1", []) for r in ok])
            j2_ag, _, j2_full = verdict_agreement([r["per_item"].get("J2", []) for r in ok])
            row["J1_item_agreement"] = j1_ag
            row["J1_items_aligned"] = j1_full
            row["J2_verdict_agreement"] = j2_ag
            if j1_ag is not None:
                j1_agreements.append(j1_ag)
            if j2_ag is not None:
                j2_agreements.append(j2_ag)
            bands = [[_j3_band(v.get("verdict")) for v in r["per_item"].get("J3", [])] for r in ok]
            bands = [b[0] for b in bands if b[0] is not None]
            if bands:
                row["J3_band_exact"] = len(set(bands)) == 1
                row["J3_band_within1"] = (max(bands) - min(bands)) <= 1
                if len(bands) >= 2:
                    # κ 矩阵索引从 0 起，档位 1..5 平移为 0..4
                    pooled_j3_pairs.extend(
                        (a - 1, b - 1) for a, b in itertools.combinations(bands, 2)
                    )
        per_sample.append(row)

    summary: dict = {"per_sample": per_sample}
    for dim in dims:
        stds = [row[dim]["std"] for row in per_sample if dim in row]
        if stds:
            summary[dim] = {
                "mean_of_std": round(statistics.mean(stds), 2),
                "max_range": round(max(row[dim]["range"] for row in per_sample if dim in row), 2),
            }
    if j1_agreements:
        summary["J1_item_agreement_mean"] = round(statistics.mean(j1_agreements), 3)
    if j2_agreements:
        summary["J2_verdict_agreement_mean"] = round(statistics.mean(j2_agreements), 3)
    if pooled_j3_pairs:
        summary["J3_pairwise_kappa_qw"] = quadratic_weighted_kappa(pooled_j3_pairs)
    return summary


def _fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


def to_markdown(payload: dict) -> str:
    s = payload["summary"]
    fz = payload["freeze"]
    lines = [
        "# E2-Judge 评委轨重复一致性实验",
        "",
        "## 方法",
        "",
        f"- 从已完成评测的样本中选 {len(payload['records'])} 个"
        "（5 曲风 basic 各 1 + constraint / hard / adversarial 各 1），"
        "冻结输入：composition.json 与 prompt 的 SHA-256 见 `judge_consistency.json` 冻结块",
        f"- 每样本独立重复 {fz['rounds']} 轮 J1/J2/J3（温度 {fz['temperature']}，"
        "与主评测一致）；规则轨为确定性代码，每样本只评一次",
        "- Judge 为生成同源的单模型单评委，本实验度量的是其重复稳定性，"
        "不涉及与人工标注的一致性",
        "",
        "## 逐样本结果",
        "",
        "| 样本 | 有效轮次 | J1 mean±std | J2 mean±std | J3 mean±std | "
        "composite 极差 | J1 清单一致率 | J2 判定一致率 | J3 严格一致 | J3 ±1 档 |",
        "|------|---------|-------------|-------------|-------------|"
        "---------------|---------------|---------------|-------------|----------|",
    ]
    for row in s["per_sample"]:
        if "J1" not in row:
            lines.append(
                f"| {row['sample_id']} | {row['rounds_ok']}（其余轮次调用失败）"
                " | - | - | - | - | - | - | - | - |"
            )
            continue
        j1a = _fmt(row.get("J1_item_agreement"), pct=True)
        j2a = _fmt(row.get("J2_verdict_agreement"), pct=True)
        lines.append(
            f"| {row['sample_id']} | {row['rounds_ok']} "
            f"| {row['J1']['mean']:.1f}±{row['J1']['std']:.2f} "
            f"| {row['J2']['mean']:.1f}±{row['J2']['std']:.2f} "
            f"| {row['J3']['mean']:.1f}±{row['J3']['std']:.2f} "
            f"| {row['composite_range']:.2f} | {j1a} | {j2a} "
            f"| {'是' if row.get('J3_band_exact') else '否'} "
            f"| {'是' if row.get('J3_band_within1') else '否'} |"
        )

    lines += [
        "",
        "## 汇总",
        "",
        f"- J1 mean(std) = {s['J1']['mean_of_std']:.2f}，最大极差 {s['J1']['max_range']:.2f}",
        f"- J2 mean(std) = {s['J2']['mean_of_std']:.2f}，最大极差 {s['J2']['max_range']:.2f}",
        f"- J3 mean(std) = {s['J3']['mean_of_std']:.2f}，最大极差 {s['J3']['max_range']:.2f}",
        f"- J1 清单逐项一致率均值：{_fmt(s.get('J1_item_agreement_mean'), pct=True)}"
        "（按输出位置对齐，轮间项数不一致的样本如实保留 n/a 或截断对齐）",
        f"- J2 约束判定一致率均值：{_fmt(s.get('J2_verdict_agreement_mean'), pct=True)}",
        f"- J3 档位二次加权 κ（合并成对比较）："
        f"{_fmt(s.get('J3_pairwise_kappa_qw'))}",
        "",
        "## 结论",
        "",
    ]
    worst = max(s[d]["mean_of_std"] for d in ("J1", "J2", "J3"))
    if worst <= 2:
        lines.append(
            "评委轨重复稳定性高（各维 mean(std) ≤ 2 分/百分制），"
            "单次采样即可作为稳定评分使用。"
        )
    elif worst <= 8:
        lines.append(
            "评委轨存在中等波动（mean(std) ≤ 8 分/百分制），"
            "排序与分组结论仍可用，但单分差异在 8 分内的样本不应据 Judge 单次评分定高下；"
            "已知缓解：对争议样本取多轮中位数。"
        )
    else:
        lines.append(
            "评委轨波动显著（mean(std) > 8 分/百分制），"
            "单次采样不满足稳定评分要求；已知缓解：正式评测改用多轮多数投票/中位数。"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    _load_env_dotenv(repo_root)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    parser.add_argument("--samples", type=Path, default=Path("evals/samples"))
    parser.add_argument("--out", type=Path, default=None, help="默认与 --results 相同")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    out_dir = args.out or args.results

    payload = run_judge_consistency(args.results, args.samples, rounds=args.rounds)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "judge_consistency.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1)
    )
    md = to_markdown(payload)
    (out_dir / "judge_consistency.md").write_text(md)
    print(md)
    print(f"written to {out_dir / 'judge_consistency.md'}")


if __name__ == "__main__":
    main()
