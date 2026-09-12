from __future__ import annotations

from miidi.eval.axes import declining
from miidi.eval.context import EvaluationContext
from miidi.musicutil.band import band


def _grams_ratio(track) -> float:
    seq = sorted(track.notes, key=lambda n: n[0])
    tokens = []
    for a, b in zip(seq, seq[1:], strict=False):
        gap = b[0] - (a[0] + a[1])
        tokens.append((a[2], a[1], gap))
    if len(tokens) < 4:
        return 0.0
    grams = [tuple(tokens[i : i + 4]) for i in range(len(tokens) - 3)]
    return (len(grams) - len(set(grams))) / len(grams)


def gate_repetition(ctx: EvaluationContext) -> float:
    ratios = [_grams_ratio(t) for t in ctx.comp.tracks if not t.is_drum and len(t.notes) >= 8]
    if not ratios:
        return 1.0
    return declining(max(ratios), 0.30, 0.90)


def gate_density(ctx: EvaluationContext) -> float:
    lo, hi = ctx.defaults.density_ref.get("__global__", (2.0, 30.0))
    total_notes = sum(len(t.notes) for t in ctx.comp.tracks if not t.is_drum)
    if total_notes == 0:
        return 1.0
    bars = max(1e-9, ctx.piece_end / ctx.bar_ticks)
    npb = total_notes / bars
    return band(npb, lo, lo * 1.25, hi * 0.8, hi, floor=0.5)


def gate_balance(ctx: EvaluationContext) -> float:
    masses = []
    for t in ctx.comp.tracks:
        if t.is_drum or not t.notes:
            continue
        masses.append(sum(n[1] for n in t.notes))
    mass_factor = 1.0
    if len(masses) >= 2:
        total = sum(masses)
        smin = min(masses) / total
        mass_factor = band(smin, 0.05, 0.10, 1.01, 1.01, floor=0.4)
    return mass_factor * _core_presence_factor(ctx)


# 每缺一条必需核心轨乘上的惩罚系数（E1 实验发现删旋律轨曾出现"删轨反升"盲区，
# 此检查是其修复闭环的一部分）
_CORE_MISSING_PENALTY = 0.6
_MIN_CORE_NOTES = 4


def _core_presence_factor(ctx: EvaluationContext) -> float:
    required = ["melody", "bass"]
    has_drum_track = any(t.is_drum for t in ctx.comp.tracks)
    if ctx.defaults.drum_patterns and has_drum_track:
        # 风格期望鼓且曲中带鼓轨时才要求其实质内容；完全不含鼓轨视为
        # prompt 驱动的织体选择（如 "just piano and vocals"），不惩罚
        required.append("drums")
    missing = 0
    for role in required:
        if not any(t.role == role and len(t.notes) >= _MIN_CORE_NOTES for t in ctx.comp.tracks):
            missing += 1
    return _CORE_MISSING_PENALTY**missing


def _pctl(sorted_xs: list[int], q: float) -> float:
    idx = min(int(q * (len(sorted_xs) - 1)), len(sorted_xs) - 1)
    return float(sorted_xs[idx])


def gate_spread(ctx: EvaluationContext) -> float:
    pitches = sorted(n[2] for t in ctx.comp.tracks if not t.is_drum for n in t.notes)
    if len(pitches) < 12:
        return 1.0
    full = _pctl(pitches, 0.95) - _pctl(pitches, 0.05)
    trimmed = pitches[3:-3]
    trim = _pctl(trimmed, 0.95) - _pctl(trimmed, 0.05)
    if full <= 0:
        return 1.0
    ratio = trim / full
    return 1.0 if ratio >= 0.6 else 0.6
