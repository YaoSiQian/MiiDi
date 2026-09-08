"""重评 J2：修复 evaluate_judge 未传入真实 prompt 导致的 J2 失效。

背景：run_eval 曾以占位符调用 evaluate_judge，J2 的显式约束抽取拿不到用户 prompt，
所有样本的 J2 退化为「全 unaddressed」的空洞高分。本脚本对每个已落盘样本只重跑
J2 一次（composition.json + 样本集 prompt → J2 判定），并同步更新
judge_report.json / results.csv / results.md。J1、J3 与规则轨结果不受影响。

用法：
    python -m evals.runners.rejudge_j2 --results evals/results --samples evals/samples
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
from pathlib import Path

import yaml

from miidi.eval.judge import (
    _extract_explicit_constraints,
    _j2_system,
    _j2_user,
    _normalize_score,
)
from miidi.llm.client import LLMClient, load_config
from miidi.schema.model import Composition


def _find_artifacts(sample_dir: Path) -> Path | None:
    for layout in (sample_dir, sample_dir / sample_dir.name):
        if (layout / "composition.json").exists():
            return layout
    return None


def _rejudge_one(client: LLMClient, sid: str, row: dict, layout: Path) -> None:
    comp = Composition.model_validate(json.loads((layout / "composition.json").read_text()))
    rule = json.loads((layout / "rule_report.json").read_text())
    judge_path = layout / "judge_report.json"
    judge = json.loads(judge_path.read_text())

    if "J_mean" in judge:
        # 幂等：该样本已重评过，只重建汇总文件，不重复调用 LLM
        j2, j_mean = judge["J2"], judge["J_mean"]
    else:
        prompt = row["_prompt"]
        constraints = _extract_explicit_constraints(comp, prompt)
        raw = client.respond_json(
            _j2_system(json.dumps(constraints, indent=2)), _j2_user(comp.model_dump(), prompt)
        )
        j2 = _normalize_score(raw)
        judge["J2"] = j2
        judge.setdefault("per_item", {})["J2"] = raw.get("per_item", [])
        j_mean = (judge["J1"] + judge["J2"] + judge["J3"]) / 3.0
        judge["J_mean"] = round(j_mean, 1)
        judge_path.write_text(json.dumps(judge, ensure_ascii=False, indent=1))

    r_rule = float(rule.get("R_rule", 0.0))
    row["J2"] = f"{j2:.1f}"
    row["J_mean"] = f"{j_mean:.1f}"
    row["composite"] = f"{0.6 * r_rule + 0.4 * j_mean:.1f}"
    print(f"[rejudged] {sid}: J2={j2:.1f} J_mean={row['J_mean']} composite={row['composite']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    prompts: dict[str, str] = {}
    for f in sorted(args.samples.glob("*.yaml")):
        data = yaml.safe_load(f.read_text()) or {}
        if data.get("id"):
            prompts[data["id"]] = data.get("prompt", "")

    csv_path = args.results / "results.csv"
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    jobs = []
    for row in rows:
        sid = row["sample_id"]
        layout = _find_artifacts(args.results / sid)
        if layout is None or sid not in prompts:
            print(f"[skip] {sid}: no artifacts or prompt", flush=True)
            continue
        if not (layout / "judge_report.json").exists():
            print(f"[skip] {sid}: no judge report (invalid composition)", flush=True)
            continue
        row["_prompt"] = prompts[sid]
        jobs.append((sid, row, layout))

    from concurrent.futures import ThreadPoolExecutor

    client = LLMClient(load_config())
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_rejudge_one, client, sid, row, layout) for sid, row, layout in jobs]
        for sid, fut in zip([j[0] for j in jobs], futures, strict=False):
            try:
                fut.result()
            except Exception as exc:
                failed.append(sid)
                print(f"[failed] {sid}: {str(exc)[:120]}", flush=True)
    client.close()

    for row in rows:
        row.pop("_prompt", None)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 重新生成 results.md（复用 run_eval 的表格渲染）
    from dataclasses import fields as dc_fields

    from evals.runners.run_eval import EvalResult, _write_markdown

    coerce = {f.name: {"float": float, "int": int}.get(f.type, str) for f in dc_fields(EvalResult)}
    results = [
        EvalResult(**{k: coerce[k](v) for k, v in r.items() if k in coerce}) for r in rows
    ]
    _write_markdown(results, args.results / "results.md")
    print(f"done: {len(jobs) - len(failed)} rejudged, {len(failed)} failed")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        main()
