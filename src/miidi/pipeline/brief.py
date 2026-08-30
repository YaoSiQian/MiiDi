from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from miidi.schema.chords import ChordParseError, parse_chord
from miidi.schema.model import (
    ChordSpan, Composition, KeySig, Meta, Section, Track, TrackRole,
)


class InstrumentSpec(BaseModel):
    name: str
    program: int = Field(ge=0, le=127)
    role: TrackRole
    description: str = ""


class MusicBrief(BaseModel):
    title: str = "untitled"
    bpm: int = Field(default=120, ge=20, le=300)
    time_signature: tuple[int, int] = (4, 4)
    tonic_pc: int = Field(default=0, ge=0, le=11)
    mode: Literal["major", "minor"] = "major"
    structure: list[Section]
    harmony: list[ChordSpan]
    instruments: list[InstrumentSpec]

    def to_skeleton(self) -> Composition:
        meta = Meta(title=self.title, bpm=self.bpm,
                    time_signature=self.time_signature,
                    key=KeySig(tonic_pc=self.tonic_pc, mode=self.mode))
        tracks = []
        for inst in self.instruments:
            tracks.append(Track(name=inst.name, program=inst.program,
                                role=inst.role, is_drum=(inst.role == "drums")))
        return Composition(meta=meta, structure=self.structure,
                           harmony=self.harmony, tracks=tracks)

    def brief_json(self) -> str:
        return self.model_dump_json()

    def piece_end_tick(self) -> int:
        """Compute the piece end tick from structure and time signature."""
        from miidi.schema.model import PPQ
        if not self.structure:
            return 0
        num, den = self.time_signature
        bar_ticks = int(PPQ * 4 * num / den)
        total_bars = max(s.start_bar + s.bars for s in self.structure)
        return int(total_bars * bar_ticks)

    @classmethod
    def validate_symbols(cls, spans: list[ChordSpan]) -> list[str]:
        errors = []
        for h in spans:
            try:
                parse_chord(h.symbol)
            except ChordParseError as exc:
                errors.append(f"chord {h.symbol!r}: {exc}")
        return errors
