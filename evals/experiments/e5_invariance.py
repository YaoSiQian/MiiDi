"""E5：无害变形不变性（IVR）实验，规则轨零 token。

无害变形（轨序重排 / 轨内音符顺序重排 / 改标题）不应改变任何规则轴分数与
R_rule；有害变形对照（音高随机化）必须严格降分。若无害变形导致分数变化，
即暴露评估器的顺序敏感性——如实报告。

用法：
    python -m evals.experiments.e5_invariance \
        --results evals/results --samples evals/samples

产出 evals/results/e5_invariance.json / .md。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.experiments.e1_discrimination import DegradationOp, degrade_composition
from evals.experiments.e2_judge_consistency import select_samples
from miidi.eval.score import evaluate_rules
from miidi.schema.model import Composition
from miidi.skills.loader import load_style_pack


def reorder_tracks(comp: Composition) -> Composition:
    return comp.model_copy(update={"tracks": list(reversed(comp.tracks))})


def shuffle_notes_in_track(comp: Composition) -> Composition:
    return comp.model_copy(
        update={"tracks": [t.model_copy(update={"notes": list(reversed(t.notes))}) for t in comp.tracks]}
    )


def rename_title(comp: Composition) -> Composition:
    return comp.model_copy(update={"meta": comp.meta.model_copy(update={"title": "IVR Probe"})})


HARMLESS = {
    "reorder_tracks": reorder_tracks,
    "shuffle_notes_in_track": shuffle_notes_in_track,
    "rename_title": rename_title,
}


def run_invariance(results_dir: Path, samples_dir: Path) -> dict:
    picks = select_samples(results_dir, samples_dir, categories=())
    if not picks:
        raise SystemExit("no usable sample dirs")
    records = []
    for i, (sid, d, sample) in enumerate(picks, 1):
        print(f"[{i}/{len(picks)}] {sid} ({sample.style})", flush=True)
        comp = Composition.model_validate(json.loads((d / "composition.json").read_text()))
        defaults = load_style_pack(sample.style).defaults
        base = evaluate_rules(comp, defaults)

        row = {
            "sample_id": sid,
            "style": sample.style,
            "R_rule": round(base.R_rule, 6),
            "transforms": {},
        }
        for name, fn in HARMLESS.items():
            report = evaluate_rules(fn(comp), defaults)
            row["transforms"][name] = {
                "R_rule_delta": round(report.R_rule - base.R_rule, 6),
                "axis_deltas": {
                    ax: round(report.axes[ax].score - base.axes[ax].score, 6)
                    for ax in base.axes
                    if ax in report.axes
                },
            }
        harmful = evaluate_rules(
            degrade_composition(comp, DegradationOp.REPEAT_FIRST_BAR), defaults
        )
        row["transforms"]["harmful_control_repeat_first_bar"] = {
            "R_rule_delta": round(harmful.R_rule - base.R_rule, 6),
        }
        # scatter_pitch 对照：在低分样本上随机化反而可能提分（见报告说明），如实记录
        scatter = evaluate_rules(
            degrade_composition(comp, DegradationOp.SCATTER_PITCH), defaults
        )
        row["transforms"]["scatter_pitch_probe"] = {
            "R_rule_delta": round(scatter.R_rule - base.R_rule, 6),
        }
        records.append(row)
        print(
            "    deltas: "
            + ", ".join(f"{k}={v['R_rule_delta']:+.4f}" for k, v in row["transforms"].items()),
            flush=True,
        )

    summary = _summarize(records)
    return {"records": records, "summary": summary}


def _summarize(records: list[dict]) -> dict:
    summary = {"samples": len(records)}
    probe_names = list(HARMLESS) + ["harmful_control_repeat_first_bar", "scatter_pitch_probe"]
    for name in probe_names:
        deltas = [r["transforms"][name]["R_rule_delta"] for r in records]
        summary[name] = {
            "all_zero": all(abs(d) < 1e-9 for d in deltas),
            "max_abs_delta": round(max(abs(d) for d in deltas), 6),
        }
    summary["harmful_all_detected"] = all(
        r["transforms"]["harmful_control_repeat_first_bar"]["R_rule_delta"] < 0 for r in records
    )
    return summary


def to_markdown(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        "# E5 无害变形不变性（IVR）实验（规则轨，零 token）",
        "",
        "## 方法",
        "",
        "- 每曲风 1 个已完成评测样本，施加三类无害变形：轨序重排、轨内音符顺序重排、"
        "改标题；规则轨分数必须完全不变",
        "- 有害对照：首小节复制（必然触发 G_repetition）必须严格降分"
        "（防「不变性=什么都检出不了」的自证）",
        "",
        "| 变形 | 全部不变 | 最大 |R_rule| 偏差 |",
        "|------|----------|----------------------|",
    ]
    for name in list(HARMLESS) + ["harmful_control_repeat_first_bar", "scatter_pitch_probe"]:
        t = s[name]
        label = "scatter_pitch（探针）" if name == "scatter_pitch_probe" else name
        lines.append(f"| {label} | {'是' if t['all_zero'] else '否'} | {t['max_abs_delta']:.6f} |")
    lines += [
        "",
        f"有害对照全部检出（Δ<0）：{'是' if s['harmful_all_detected'] else '否'}",
        "",
        "scatter_pitch 探针：对低分样本（基线 R_rule < 25）随机化音高反而可能提分"
        "——随机 48–84 音高比原曲更贴合，属「退化操作≠必然有害」的边界条件，"
        "与 E3 删轨反升同类；故有害对照改用必触发 G_repetition 的首小节复制。",
        "若无害变形出现非零偏差，说明对应评估轴存在顺序敏感性，需修复或披露；"
        "本次运行结果如上表所示。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evals/results"))
    parser.add_argument("--samples", type=Path, default=Path("evals/samples"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out or args.results

    payload = run_invariance(args.results, args.samples)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "e5_invariance.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    md = to_markdown(payload)
    (out_dir / "e5_invariance.md").write_text(md)
    print(md)
    print(f"written to {out_dir / 'e5_invariance.md'}")


if __name__ == "__main__":
    main()
