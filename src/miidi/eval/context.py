from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from miidi.eval.style import StyleDefaults
from miidi.musicutil.scales import scale_pcs
from miidi.schema.chords import ChordInfo, parse_chord
from miidi.schema.model import Composition


@dataclass(frozen=True)
class NoteRef:
    track_index: int
    track_name: str
    role: str
    onset: int
    dur: int
    pitch: int
    velocity: int

    @property
    def end(self) -> int:
        return self.onset + self.dur


@dataclass(frozen=True)
class Vertical:
    pitch_classes: frozenset[int]
    pitches: list[int]


@dataclass
class EvaluationContext:
    comp: Composition
    defaults: StyleDefaults
    sections: list[tuple[str, int, int]]
    piece_end: int

    @classmethod
    def from_composition(cls, comp: Composition,
                         defaults: StyleDefaults | None = None) -> "EvaluationContext":
        defaults = defaults or StyleDefaults()
        bar = comp.bar_ticks
        if comp.structure:
            sections = [(s.name, s.start_bar * bar, int((s.start_bar + s.bars) * bar))
                        for s in comp.structure]
        else:
            end = max((t.end_tick for t in comp.tracks), default=bar)
            sections = [("all", 0, max(end, bar))]
        piece_end = max(comp.piece_end_tick(), sections[-1][2])
        return cls(comp=comp, defaults=defaults, sections=sections, piece_end=piece_end)

    @property
    def bar_ticks(self) -> int:
        return self.comp.bar_ticks

    @property
    def key(self):
        return self.comp.meta.key

    @property
    def scale(self) -> frozenset[int]:
        return scale_pcs(self.key)

    def _chord_timeline(self) -> list[tuple[int, int, ChordInfo | None]]:
        if not hasattr(self, "_timeline"):
            bar = self.bar_ticks
            timeline = []
            for h in sorted(self.comp.harmony, key=lambda h: h.bar):
                try:
                    info: ChordInfo | None = parse_chord(h.symbol)
                except Exception:
                    info = None
                timeline.append((h.bar * bar, int(round((h.bar + h.dur_bars) * bar)), info))
            self._timeline = timeline
        return self._timeline

    def chord_at(self, tick: int) -> ChordInfo | None:
        for start, end, info in self._chord_timeline():
            if start <= tick < end:
                return info
        return None

    def flat_notes(self, exclude_drum: bool = True) -> list[NoteRef]:
        if not hasattr(self, "_flat_cache"):
            self._flat_cache: dict[bool, list[NoteRef]] = {}
        if exclude_drum not in self._flat_cache:
            refs = []
            for ti, t in enumerate(self.comp.tracks):
                if exclude_drum and t.is_drum:
                    continue
                for onset, dur, pitch, vel in t.notes:
                    refs.append(NoteRef(ti, t.name, t.role, onset, dur, pitch, vel))
            self._flat_cache[exclude_drum] = refs
        return self._flat_cache[exclude_drum]

    def sounding_at(self, tick: int, exclude_drum: bool = True) -> list[NoteRef]:
        return [n for n in self.flat_notes(exclude_drum) if n.onset <= tick < n.end]

    def iterate_verticals(self, step: int = 240) -> Iterator[tuple[int, Vertical]]:
        cache: dict[int, Vertical] = {}
        for tick in range(0, max(self.piece_end, step), step):
            if tick not in cache:
                notes = self.sounding_at(tick)
                cache[tick] = Vertical(
                    pitch_classes=frozenset(n.pitch % 12 for n in notes),
                    pitches=sorted(n.pitch for n in notes),
                )
            yield tick, cache[tick]

    def track_of_role(self, role: str):
        for t in self.comp.tracks:
            if t.role == role:
                return t
        return None

    def section_of_tick(self, tick: int) -> int:
        for i, (_n, s, e) in enumerate(self.sections):
            if s <= tick < e:
                return i
        return len(self.sections) - 1
