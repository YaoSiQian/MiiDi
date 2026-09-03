from __future__ import annotations

from dataclasses import dataclass, field

from miidi.eval.context import EvaluationContext
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
    return (1.0, []) if not viols else (0.0, viols)


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
        sounding = [
            n for n in ctx.flat_notes() if n.role in ACCOMP_ROLES and n.onset < t1 and n.end > t0
        ]
        if not sounding:
            continue
        mass = sum(min(n.end, t1) - max(n.onset, t0) for n in sounding)
        in_mass = sum(
            min(n.end, t1) - max(n.onset, t0) for n in sounding if n.pitch % 12 in chord.pcs
        )
        supports.append(in_mass / mass if mass else 0.0)
        vert = {n.pitch % 12 for n in sounding}
        matches.append(len(vert & chord.pcs) / len(chord.pcs))
    support = (
        band(sum(supports) / len(supports), 0.5, 0.8, 1.01, 1.01, floor=0.3) if supports else 0.5
    )
    declaration = sum(matches) / len(matches) if matches else 0.7

    verts = list(ctx.iterate_verticals())
    clustered = sum(
        1 for _t, v in verts if v.pitch_classes and _min_adjacent_semitone(v.pitch_classes) <= 1
    )
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

    score = (
        0.30 * max(adherence, 0.0)
        + 0.30 * support
        + 0.15 * declaration
        + 0.15 * (1.0 - min(cluster_rate, 1.0))
        + 0.10 * cadence
    )
    return AxisResult(
        score=max(0.0, min(1.0, score)),
        details={
            "scale_adherence": max(adherence, 0.0),
            "chord_support": support,
            "declaration_match": declaration,
            "cluster_rate": cluster_rate,
            "cadence_rate": cadence,
        },
    )


_GRID_KS = (1, 2, 3, 4, 6, 8, 12)


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def axis_voice(ctx: EvaluationContext) -> AxisResult:
    from miidi.musicutil.gm import play_comf

    play_fracs: list[float] = []
    comf_fracs: list[float] = []
    leaps = 0
    steps = 0
    role_means: dict[str, float] = {}
    for t in ctx.comp.tracks:
        if t.is_drum or not t.notes:
            continue
        play_rng, comf_rng = play_comf(t.program)
        play_fracs.append(
            sum(1 for n in t.notes if play_rng[0] <= n[2] <= play_rng[1]) / len(t.notes)
        )
        comf_fracs.append(
            sum(1 for n in t.notes if comf_rng[0] <= n[2] <= comf_rng[1]) / len(t.notes)
        )
        seq = sorted(t.notes, key=lambda n: n[0])
        for a, b in zip(seq, seq[1:]):
            if b[0] >= a[0] + a[1]:
                steps += 1
                if abs(b[2] - a[2]) > 12:
                    leaps += 1
        bucket = "melody" if t.role in ("melody", "counter") else t.role
        role_means[bucket] = _mean([n[2] for n in t.notes])
    play_frac = min(play_fracs) if play_fracs else 1.0
    comf_frac = min(comf_fracs) if comf_fracs else 1.0
    range_fit = 0.6 * play_frac + 0.4 * comf_frac
    leap_rate = leaps / steps if steps else 0.0

    melodic = [t for t in ctx.comp.tracks if not t.is_drum and t.notes]
    parallels = 0
    for i in range(len(melodic)):
        for j in range(i + 1, len(melodic)):
            ta = sorted(melodic[i].notes, key=lambda n: n[0])
            tb = sorted(melodic[j].notes, key=lambda n: n[0])
            k = 0
            prev: int | None = None
            for na in ta:
                while k < len(tb) and tb[k][0] + tb[k][1] <= na[0]:
                    k += 1
                if k >= len(tb):
                    break
                nb = tb[k]
                interval = abs(na[2] - nb[2]) % 12
                if interval in (0, 7):
                    if prev == interval:
                        parallels += 1
                    prev = interval
                else:
                    prev = None

    mel_mean = next((v for r, v in role_means.items() if r == "melody"), None)
    bass_mean = next((v for r, v in role_means.items() if r == "bass"), None)
    if mel_mean is None or bass_mean is None:
        gap_component = 0.8
    else:
        gap_component = band(abs(mel_mean - bass_mean), 8, 14, 48, 60, floor=0.4)

    par_component = 1.0 - min(parallels, 3) / 3
    leap_component = declining(leap_rate, 0.10, 0.40)
    score = 0.40 * range_fit + 0.25 * par_component + 0.20 * leap_component + 0.15 * gap_component
    return AxisResult(
        score=max(0.0, min(1.0, score)),
        details={
            "range_fit": range_fit,
            "parallel_count": parallels,
            "leap_rate": leap_rate,
            "register_gap": gap_component,
        },
    )


_DRUM_PITCH_BY_NAME = {"kick": 36, "snare": 38, "hat": 42}


def axis_rhythm(ctx: EvaluationContext) -> AxisResult:
    swing = set(ctx.defaults.swing_offsets)
    onsets = [n[0] for t in ctx.comp.tracks for n in t.notes]
    if onsets:
        legal = sum(
            1 for o in onsets if any((o * k) % 480 == 0 for k in _GRID_KS) or o % 480 in swing
        )
        grid = legal / len(onsets)
    else:
        grid = 1.0

    bar = ctx.bar_ticks
    dens_components: list[float] = []
    for t in ctx.comp.tracks:
        ref = ctx.defaults.density_ref.get(t.role)
        if ref is None or not t.notes:
            continue
        span_bars = max(1, round(t.end_tick / bar))
        per_bar = len(t.notes) / span_bars
        dens_components.append(
            band(per_bar, ref[0], ref[0] * 1.25, ref[1] * 0.8, ref[1], floor=0.3)
        )
    density = sum(dens_components) / len(dens_components) if dens_components else 1.0

    drum_track = next((t for t in ctx.comp.tracks if t.is_drum), None)
    if drum_track and ctx.defaults.drum_patterns:
        fits: list[float] = []
        for name, residues in ctx.defaults.drum_patterns.items():
            pitch = _DRUM_PITCH_BY_NAME.get(name)
            if pitch is None:
                continue
            actual = {n[0] % bar for n in drum_track.notes if n[2] == pitch}
            allowed = set(residues)
            fits.append(len(actual & allowed) / max(len(allowed), 1))
        drum_fit = sum(fits) / len(fits) if fits else 1.0
    else:
        drum_fit = 1.0

    offbeat = sorted(o % 480 for o in onsets if not any((o * k) % 480 == 0 for k in _GRID_KS))
    if len(offbeat) >= 4:
        spread = max(offbeat) - min(offbeat)
        swing_consistency = 1.0 - min(spread / 120, 1.0) * 0.8
    else:
        swing_consistency = 1.0

    score = 0.30 * grid + 0.30 * density + 0.25 * drum_fit + 0.15 * swing_consistency
    return AxisResult(
        score=max(0.0, min(1.0, score)),
        details={
            "grid_adherence": grid,
            "density_fit": density,
            "drum_pattern_fit": drum_fit,
            "swing_consistency": swing_consistency,
        },
    )


import math as _math
import re as _re


def _family(name: str) -> str:
    return _re.sub(r"\d+$", "", name.strip().lower()) or name.strip().lower()


def _section_vectors(ctx: EvaluationContext) -> list[dict]:
    vectors = []
    for _si, (name, start, end) in enumerate(ctx.sections):
        notes = [n for n in ctx.flat_notes() if start <= n.onset < end]
        hist = [0.0] * 12
        for n in notes:
            hist[n.pitch % 12] += n.dur
        total = sum(hist) or 1.0
        hist = [h / total for h in hist]
        bars = max(1e-9, (end - start) / ctx.bar_ticks)
        density = len(notes) / bars
        vel = _mean([float(n.velocity) for n in notes]) or 0.0
        vectors.append({"name": name, "hist": hist, "density": density, "vel": vel})
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = _math.sqrt(sum(x * x for x in a))
    nb = _math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def axis_structure(ctx: EvaluationContext) -> AxisResult:
    spans = sorted(ctx.sections, key=lambda s: s[1])
    covered = 0
    cursor = 0
    for _n, s, e in spans:
        start = max(s, cursor)
        if e > start:
            covered += e - start
        cursor = max(cursor, e)
    coverage = covered / max(ctx.piece_end, 1)
    coverage_component = 1.0 - min(max(1.0 - coverage, 0.0) * 4, 1.0)

    vecs = _section_vectors(ctx)
    sims: dict[tuple[str, str], list[float]] = {}
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            fa, fb = _family(vecs[i]["name"]), _family(vecs[j]["name"])
            va = vecs[i]["hist"] + [vecs[i]["density"] / 16.0, vecs[i]["vel"] / 128.0]
            vb = vecs[j]["hist"] + [vecs[j]["density"] / 16.0, vecs[j]["vel"] / 128.0]
            key = (fa, fb) if fa <= fb else (fb, fa)
            sims.setdefault(key, []).append(_cosine(va, vb))
    repeat_vals = [v for (fa, fb), vs in sims.items() if fa == fb for v in vs]
    contrast_vals = [v for (fa, fb), vs in sims.items() if fa != fb for v in vs]
    repeat_sim = _mean(repeat_vals) if repeat_vals else None
    contrast_sim = _mean(contrast_vals) if contrast_vals else None
    repeat_component = (
        band(repeat_sim, 0.55, 0.70, 1.01, 1.01, floor=0.2) if repeat_sim is not None else 0.8
    )
    contrast_component = (
        (1.0 - band(contrast_sim, 0.90, 0.95, 1.01, 1.01, floor=0.0))
        if contrast_sim is not None
        else 0.8
    )

    densities = [v["density"] for v in vecs]
    shape = band(_std(densities), 0.3, 0.8, 8.0, 12.0, floor=0.2) if len(densities) >= 2 else 0.8

    melody = ctx.track_of_role("melody")
    recall = 0.8
    if melody and len(ctx.sections) >= 2 and len(melody.notes) >= 4:
        first = [
            n for n in sorted(melody.notes, key=lambda n: n[0]) if ctx.section_of_tick(n[0]) == 0
        ]
        rest = [
            n for n in sorted(melody.notes, key=lambda n: n[0]) if ctx.section_of_tick(n[0]) > 0
        ]
        if len(first) >= 4 and rest:
            target = _contour(first[:8])
            found = (
                any(_has_contour(rest[i : i + 8], target) for i in range(max(len(rest) - 7, 0)))
                if len(target) >= 2
                else False
            )
            recall = 1.0 if found else 0.3

    score = (
        0.25 * coverage_component
        + 0.25 * repeat_component
        + 0.25 * contrast_component
        + 0.15 * shape
        + 0.10 * recall
    )
    return AxisResult(
        score=max(0.0, min(1.0, score)),
        details={
            "coverage": coverage_component,
            "repeat_family_sim": repeat_sim if repeat_sim is not None else -1.0,
            "contrast_family_sim": contrast_sim if contrast_sim is not None else -1.0,
            "contour_shape": shape,
            "motif_recall": recall,
        },
    )


def _std(xs: list[float]) -> float:
    m = _mean(xs)
    if m is None:
        return 0.0
    return _math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _contour(notes) -> list[int]:
    seq = sorted(notes, key=lambda n: n[0])
    out: list[int] = []
    for a, b in zip(seq, seq[1:]):
        d = b[2] - a[2]
        out.append((d > 0) - (d < 0))
    while out and out[0] == 0:
        out.pop(0)
    return out


def _has_contour(notes, target: list[int]) -> bool:
    return bool(target) and _contour(notes) == target


_CHORUS = {"chorus", "refrain", "hook"}
_VERSE = {"verse", "couplet"}


def _bar_mean_velocities(ctx: EvaluationContext) -> list[float]:
    bar = ctx.bar_ticks
    buckets: dict[int, list[float]] = {}
    for n in ctx.flat_notes():
        buckets.setdefault(n.onset // bar, []).append(float(n.velocity))
    return [_mean(vs) for _b, vs in sorted(buckets.items())]


def _lag1_autocorr(xs: list[float]) -> float | None:
    m = _mean(xs)
    if m is None or len(xs) < 4:
        return None
    var = sum((x - m) ** 2 for x in xs)
    if var <= 0.0:
        return None
    num = sum((xs[i] - m) * (xs[i + 1] - m) for i in range(len(xs) - 1))
    return num / var


def axis_dynamics(ctx: EvaluationContext) -> AxisResult:
    vels = [float(n.velocity) for n in ctx.flat_notes()]
    sigma = _std(vels)
    spread_component = band(sigma, 4, 8, 45, 60, floor=0.1)

    ac = _lag1_autocorr(_bar_mean_velocities(ctx))
    if ac is None:
        directionality = 0.8
    else:
        directionality = band(ac, 0.15, 0.30, 1.01, 1.01, floor=0.0)

    chorus_vels = [v["vel"] for v in _section_vectors(ctx) if _family(v["name"]) in _CHORUS]
    verse_vels = [v["vel"] for v in _section_vectors(ctx) if _family(v["name"]) in _VERSE]
    if chorus_vels and verse_vels:
        diff = _mean(chorus_vels) - _mean(verse_vels)
        gradient = band(diff, -5.0, 0.0, 60.0, 61.0, floor=0.2)
    else:
        gradient = 0.8

    score = 0.5 * spread_component + 0.25 * directionality + 0.25 * gradient
    return AxisResult(
        score=max(0.0, min(1.0, score)),
        details={
            "velocity_spread": spread_component,
            "directionality": directionality,
            "gradient_ok": gradient,
        },
    )
