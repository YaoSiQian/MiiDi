from __future__ import annotations

import contextlib
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from evals.schema import EvalSample
from miidi.eval.composite import compute_composite
from miidi.eval.judge import evaluate_judge
from miidi.eval.score import GATE_NAMES, RuleReport, evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.pipeline.orchestrator import run_pipeline
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack

AXIS_NAMES = ("harmony", "voice", "rhythm", "structure", "dynamics")


@dataclass
class EvalResult:
    sample_id: str
    style: str
    category: str = ""
    R_rule: float = 0.0
    J1: float = 0.0
    J2: float = 0.0
    J3: float = 0.0
    J_mean: float = 0.0
    composite: float = 0.0
    harmony: float = 0.0
    voice: float = 0.0
    rhythm: float = 0.0
    structure: float = 0.0
    dynamics: float = 0.0
    gate_repetition: float = 0.0
    gate_density: float = 0.0
    gate_balance: float = 0.0
    gate_spread: float = 0.0
    note_count: int = 0
    track_count: int = 0
    duration_bars: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def run_single_sample(sample: EvalSample, client: LLMClient, out_dir: Path) -> EvalResult:
    result = EvalResult(sample_id=sample.id, style=sample.style, category=sample.sample_type)
    try:
        pack = load_style_pack(sample.style)
        pipeline_result = run_pipeline(
            sample.prompt, sample.style, client, out_dir=out_dir, store=None
        )
        if pipeline_result.comp is None:
            result.error = "generation failed"
            return result
        comp = pipeline_result.comp
        result.note_count = sum(len(t.notes) for t in comp.tracks)
        result.track_count = len(comp.tracks)
        result.duration_bars = int(comp.total_bars())

        rule_report = evaluate_rules(comp, pack.defaults)
        result.R_rule = rule_report.R_rule
        _save_artifacts(out_dir, comp, rule_report)

        if not rule_report.invalid:
            for name in AXIS_NAMES:
                if name in rule_report.axes:
                    setattr(result, name, round(rule_report.axes[name].score * 100, 1))
            for name in GATE_NAMES:
                if name in rule_report.gates:
                    setattr(result, f"gate_{name}", round(rule_report.gates[name], 3))

            judge_report = evaluate_judge(comp, rule_report, client, sample.style, sample.prompt)
            result.J1 = judge_report.J1
            result.J2 = judge_report.J2
            result.J3 = judge_report.J3
            result.J_mean = round((judge_report.J1 + judge_report.J2 + judge_report.J3) / 3, 1)
            _save_judge(out_dir, judge_report)

            composite = compute_composite(rule_report, judge_report)
            result.composite = composite.composite
        else:
            result.composite = 0.0
            result.error = "invalid composition"
    except Exception as exc:
        result.error = str(exc)[:200]
    return result


def _save_artifacts(sample_dir: Path, comp: Composition, rule_report: RuleReport) -> None:
    # 逐样本产物尽力落盘（供失败模式分析），失败不影响评分主流程
    with contextlib.suppress(Exception):
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / "composition.json").write_text(
            json.dumps(comp.model_dump(mode="json", warnings=False), ensure_ascii=False, indent=1)
        )
        (sample_dir / "rule_report.json").write_text(
            json.dumps(rule_report.to_dict(), ensure_ascii=False, indent=1)
        )


def _save_judge(sample_dir: Path, judge_report: object) -> None:
    with contextlib.suppress(Exception):
        (sample_dir / "judge_report.json").write_text(
            json.dumps(judge_report.to_dict(), ensure_ascii=False, indent=1)  # type: ignore[attr-defined]
        )


def run_eval(
    samples_dir: Path,
    out_dir: Path,
    client: LLMClient | None = None,
    limit: int | None = None,
    workers: int = 1,
) -> list[EvalResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for f in sorted(samples_dir.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        samples.append(EvalSample(**data))
    if limit is not None:
        samples = samples[:limit]

    def _task(sample: EvalSample) -> EvalResult:
        c = LLMClient(load_config()) if client is None else client
        return run_single_sample(sample, c, out_dir / sample.id)

    if workers <= 1:
        results = []
        for i, sample in enumerate(samples):
            print(f"[{i + 1}/{len(samples)}] {sample.id} ({sample.style})", flush=True)
            results.append(_task(sample))
            _write_csv(results, out_dir / "results.csv")
            _write_markdown(results, out_dir / "results.md")
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(samples)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_task, s): i for i, s in enumerate(samples)}
            for j, fut in enumerate(as_completed(futures), 1):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                    print(f"[{j}/{len(samples)}] {samples[idx].id} done", flush=True)
                except Exception as exc:
                    results[idx] = EvalResult(
                        sample_id=samples[idx].id,
                        style=samples[idx].style,
                        category=samples[idx].sample_type,
                        error=str(exc)[:200],
                    )
                    print(f"[{j}/{len(samples)}] {samples[idx].id} FAILED: {exc}", flush=True)
                # 增量落盘：长跑中断时已完成样本不丢
                _write_csv([r for r in results if r is not None], out_dir / "results.csv")
                _write_markdown([r for r in results if r is not None], out_dir / "results.md")

    _write_csv(results, out_dir / "results.csv")
    _write_markdown(results, out_dir / "results.md")
    return results


def _write_csv(results: list[EvalResult], path: Path) -> None:
    if not results:
        return
    fieldnames = list(results[0].to_dict().keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())


def _write_markdown(results: list[EvalResult], path: Path) -> None:
    lines = ["# Evaluation Results\n"]
    lines.append("| Sample | Category | Style | R_rule | J1 | J2 | J3 | J_mean | Composite | Error |")
    lines.append("|--------|----------|-------|--------|----|----|----|--------|-----------|-------|")
    for r in results:
        err = r.error[:30] if r.error else ""
        lines.append(
            f"| {r.sample_id} | {r.category} | {r.style} | {r.R_rule:.1f} | "
            f"{r.J1:.1f} | {r.J2:.1f} | {r.J3:.1f} | {r.J_mean:.1f} | "
            f"{r.composite:.1f} | {err} |"
        )
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max number of samples to evaluate")
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    run_eval(args.samples, args.out, limit=args.limit, workers=args.workers)
