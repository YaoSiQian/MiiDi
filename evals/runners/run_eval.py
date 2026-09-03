from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from evals.samples.schema import EvalSample
from miidi.eval.composite import compute_composite
from miidi.eval.judge import evaluate_judge
from miidi.eval.score import evaluate_rules
from miidi.llm.client import LLMClient, load_config
from miidi.pipeline.orchestrator import run_pipeline
from miidi.skills.loader import load_style_pack


@dataclass
class EvalResult:
    sample_id: str
    style: str
    R_rule: float = 0.0
    J1: float = 0.0
    J2: float = 0.0
    J3: float = 0.0
    composite: float = 0.0
    note_count: int = 0
    track_count: int = 0
    duration_bars: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def run_single_sample(sample: EvalSample, client: LLMClient, out_dir: Path) -> EvalResult:
    result = EvalResult(sample_id=sample.id, style=sample.style)
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

        if not rule_report.invalid:
            judge_report = evaluate_judge(comp, rule_report, client, sample.style)
            result.J1 = judge_report.J1
            result.J2 = judge_report.J2
            result.J3 = judge_report.J3
            composite = compute_composite(rule_report, judge_report)
            result.composite = composite.composite
        else:
            result.composite = 0.0
            result.error = "invalid composition"
    except Exception as exc:
        result.error = str(exc)[:200]
    return result


def run_eval(
    samples_dir: Path, out_dir: Path, client: LLMClient | None = None, limit: int | None = None
) -> list[EvalResult]:
    if client is None:
        client = LLMClient(load_config())
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for f in sorted(samples_dir.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        samples.append(EvalSample(**data))
    if limit is not None:
        samples = samples[:limit]
    results = []
    for i, sample in enumerate(samples):
        print(f"[{i + 1}/{len(samples)}] {sample.id} ({sample.style})")
        result = run_single_sample(sample, client, out_dir / sample.id)
        results.append(result)
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
    lines.append("| Sample | Style | R_rule | J1 | J2 | J3 | Composite | Error |")
    lines.append("|--------|-------|--------|-----|-----|-----|-----------|-------|")
    for r in results:
        err = r.error[:30] if r.error else ""
        lines.append(
            f"| {r.sample_id} | {r.style} | {r.R_rule:.1f} | "
            f"{r.J1:.1f} | {r.J2:.1f} | {r.J3:.1f} | "
            f"{r.composite:.1f} | {err} |"
        )
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max number of samples to evaluate")
    args = parser.parse_args()
    run_eval(args.samples, args.out, limit=args.limit)
