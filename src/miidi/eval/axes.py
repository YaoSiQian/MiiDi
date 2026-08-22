from __future__ import annotations

from dataclasses import dataclass, field

from miidi.eval.context import EvaluationContext, Vertical
from miidi.musicutil.band import band
from miidi.musicutil.scales import minor_superset_pcs
from miidi.schema.model import Composition
from miidi.schema.validate import Violation, validate_composition

ACCOMP_ROLES = {"bass", "harmony", "color", "counter"}


@dataclass
class AxisResult:
    score: float
    details: dict = field(default_factory=dict)


def declining(x: float, ok_until: float, zero_at: float) -> float:
    if x <= ok_until:
        return 1.0
    if x >= zero_at:
        return 0.0
    return 1.0 - (x - ok_until) / (zero_at - ok_until)


def _min_adjacent_semitone(pcs: frozenset[int]) -> int:
    s = sorted(pcs)
    best = 12
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            d = (s[j] - s[i]) % 12
            best = min(best, min(d, 12 - d))
    return best


def axis_format(comp: Composition) -> tuple[float, list[Violation]]:
    viols = validate_composition(comp)
    return ((1.0, []) if not viols else (0.0, viols))


def axis_harmony(ctx: EvaluationContext) -> AxisResult:
    key = ctx.key
    allowed = ctx.scale if key.mode == "major" else ctx.scale | minor_superset_pcs(key)
    notes = [(n.onset, n.pitch) for n in ctx.flat_notes()]
    total = len(notes)
    if total == 0:
        adherence = 0.5
    else:
        weak_cap = int(0.15 * total)
        strong_off = 0
        weak_off = 0
        for onset, pitch in notes:
            if pitch % 12 in allowed:
                continue
            if onset % 240 != 0:
                weak_off += 1
            else:
                strong_off += 1
        adherence = 1.0 - (strong_off + max(0, weak_off - weak_cap)) / total

    bar = ctx.bar_ticks
    n_bars = max(1, ctx.piece_end // bar)
    supports: list[float] = []
    matches: list[float] = []
    for b in range(n_bars):
        t0, t1 = b * bar, (b + 1) * bar
        chord = ctx.chord_at(t0)
        if chord is None:
            continue
        sounding = [n for n in ctx.flat_notes()
                    if n.role in ACCOMP_ROLES and n.onset < t1 and n.end > t0]
        if not sounding:
            continue
        mass = sum(min(n.end, t1) - max(n.onset, t0) for n in sounding)
        in_mass = sum(min(n.end, t1) - max(n.onset, t0) for n in sounding
                      if n.pitch % 12 in chord.pcs)
        supports.append(in_mass / mass if mass else 0.0)
        vert = {n.pitch % 12 for n in sounding}
        matches.append(len(vert & chord.pcs) / len(chord.pcs))
    support = band(sum(supports) / len(supports), 0.5, 0.8, 1.01, 1.01, floor=0.3) \
        if supports else 0.5
    declaration = sum(matches) / len(matches) if matches else 0.7

    verts = list(ctx.iterate_verticals())
    clustered = sum(1 for _t, v in verts
                    if v.pitch_classes and _min_adjacent_semitone(v.pitch_classes) <= 1)
    cluster_rate = clustered / max(len(verts), 1)

    hits = 0
    checked = 0
    for _name, _start, end in ctx.sections:
        now = ctx.chord_at(max(end - 1, 0))
        prev = ctx.chord_at(max(end - 1 - bar, 0))
        if now is None:
            continue
        checked += 1
        deg_now = (now.root_pc - key.tonic_pc) % 12
        deg_prev = (prev.root_pc - key.tonic_pc) % 12 if prev else None
        if deg_now == 0 and deg_prev in (7, 5):
            hits += 1
    cadence = (hits / checked) if checked else 0.7

    score = (0.30 * max(adherence, 0.0) + 0.30 * support + 0.15 * declaration
             + 0.15 * (1.0 - min(cluster_rate, 1.0)) + 0.10 * cadence)
    return AxisResult(score=max(0.0, min(1.0, score)), details={
        "scale_adherence": max(adherence, 0.0),
        "chord_support": support,
        "declaration_match": declaration,
        "cluster_rate": cluster_rate,
        "cadence_rate": cadence,
    })
