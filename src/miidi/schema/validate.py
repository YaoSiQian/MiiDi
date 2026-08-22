from __future__ import annotations

from dataclasses import dataclass

from miidi.schema.model import Composition


@dataclass(frozen=True)
class Violation:
    location: str
    code: str
    message: str


def validate_composition(comp: Composition) -> list[Violation]:
    out: list[Violation] = []
    if comp.structure:
        limit = int(comp.total_bars() * comp.bar_ticks)
    else:
        limit = comp.piece_end_tick()
    for track in comp.tracks:
        prefix = track.name
        if track.is_drum != (track.role == "drums"):
            out.append(Violation(prefix, "DRUM_ROLE",
                                 f"is_drum={track.is_drum} conflicts with role={track.role!r}"))
        uniq_spans: set[tuple[int, int]] = set()
        ordered: list[tuple[int, int]] = []
        for ni, (onset, dur, pitch, vel) in enumerate(track.notes):
            loc = f"{prefix}/note{ni}"
            if not 0 <= pitch <= 127:
                out.append(Violation(loc, "PITCH_RANGE", f"pitch {pitch} outside [0,127]"))
            if not 1 <= vel <= 127:
                out.append(Violation(loc, "VELOCITY_RANGE", f"velocity {vel} outside [1,127]"))
            if onset < 0 or dur < 1:
                out.append(Violation(loc, "BOUNDS", f"bad span onset={onset} dur={dur}"))
                continue
            if limit and onset + dur > limit:
                out.append(Violation(loc, "BOUNDS",
                                     f"ends at {onset + dur} beyond piece length {limit}"))
            span = (onset, dur)
            if span not in uniq_spans:
                uniq_spans.add(span)
                ordered.append(span)
        if track.is_drum:
            continue
        spans = sorted(ordered)
        for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
            if b0 < a1:
                out.append(Violation(prefix, "OVERLAP",
                                     f"spans [{a0},{a1}) and [{b0},{b1}) overlap"))
    return out
