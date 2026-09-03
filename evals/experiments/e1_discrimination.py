from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.schema.model import Composition


class DegradationOp(Enum):
    SCATTER_PITCH = "scatter_pitch"
    REMOVE_TRACK = "remove_track"
    SCATTER_ONSET = "scatter_onset"
    REPEAT_FIRST_BAR = "repeat_first_bar"


# Which axis each degradation operator should primarily affect
# Maps op -> list of (axis_name, expected_min_drop)
ATTRIBUTION_TARGETS: dict[DegradationOp, list[tuple[str, float]]] = {
    DegradationOp.SCATTER_PITCH: [("harmony", 0.2), ("voice", 0.15)],
    DegradationOp.REMOVE_TRACK: [("harmony", 0.1), ("voice", 0.1)],
    DegradationOp.SCATTER_ONSET: [("rhythm", 0.2)],
    DegradationOp.REPEAT_FIRST_BAR: [("structure", 0.15), ("rhythm", 0.1)],
}


def degrade_composition(comp: Composition, op: DegradationOp, seed: int = 42) -> Composition:
    rng = random.Random(seed)
    new_tracks = []
    for track in comp.tracks:
        new_notes = list(track.notes)
        if op == DegradationOp.SCATTER_PITCH:
            new_notes = [(o, d, rng.randint(48, 84), v) for o, d, p, v in new_notes]
        elif op == DegradationOp.SCATTER_ONSET:
            new_notes = [(o + rng.randint(-60, 60), d, p, v) for o, d, p, v in new_notes]
        elif op == DegradationOp.REPEAT_FIRST_BAR:
            bar_ticks = comp.bar_ticks
            first_bar_notes = [n for n in new_notes if n[0] < bar_ticks]
            repeated = []
            total_bars = int(comp.total_bars())
            for bar in range(total_bars):
                for onset, dur, pitch, vel in first_bar_notes:
                    new_onset = onset + bar * bar_ticks
                    if new_onset + dur <= total_bars * bar_ticks:
                        repeated.append((new_onset, dur, pitch, vel))
            new_notes = repeated
        new_tracks.append(track.model_copy(update={"notes": new_notes}))

    if op == DegradationOp.REMOVE_TRACK and len(new_tracks) > 1:
        new_tracks = new_tracks[:-1]

    return comp.model_copy(update={"tracks": new_tracks})


@dataclass
class AttributionResult:
    op: DegradationOp
    axis_drops: dict[str, float]
    expected_axes: list[str]
    passed: bool
    details: list[str]


def check_attribution(
    original: Composition,
    degraded: Composition,
    op: DegradationOp,
    defaults: StyleDefaults | None = None,
) -> AttributionResult:
    report_orig = evaluate_rules(original, defaults)
    report_deg = evaluate_rules(degraded, defaults)
    targets = ATTRIBUTION_TARGETS.get(op, [])
    expected_axes = [ax for ax, _ in targets]
    axis_drops = {}
    details = []
    all_pass = True
    for axis_name, min_drop in targets:
        orig_score = report_orig.axes.get(axis_name)
        deg_score = report_deg.axes.get(axis_name)
        if orig_score is None or deg_score is None:
            details.append(f"axis {axis_name} not found in report")
            all_pass = False
            continue
        drop = orig_score.score - deg_score.score
        axis_drops[axis_name] = round(drop, 4)
        if drop < min_drop:
            details.append(f"axis {axis_name}: drop {drop:.3f} < expected min {min_drop:.3f}")
            all_pass = False
        else:
            details.append(f"axis {axis_name}: drop {drop:.3f} >= expected min {min_drop:.3f}")
    for ax, res in report_orig.axes.items():
        if ax not in axis_drops:
            deg_res = report_deg.axes.get(ax)
            if deg_res is not None:
                axis_drops[ax] = round(res.score - deg_res.score, 4)
    return AttributionResult(
        op=op,
        axis_drops=axis_drops,
        expected_axes=expected_axes,
        passed=all_pass,
        details=details,
    )
