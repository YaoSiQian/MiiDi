from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

PPQ = 480

TrackRole = Literal["melody", "harmony", "bass", "counter", "color", "drums"]

OnsetTick = Annotated[int, Field(ge=0)]
Velocity = Annotated[int, Field(ge=0, le=127)]

_TIME_SIGNATURE_DENOMINATORS = (2, 4, 8, 16)


class KeySig(BaseModel):
    tonic_pc: int = Field(ge=0, le=11)
    mode: Literal["major", "minor"] = "major"


class Meta(BaseModel):
    title: str = "untitled"
    bpm: int = Field(default=120, ge=20, le=300)
    time_signature: tuple[int, int] = (4, 4)
    key: KeySig = KeySig(tonic_pc=0)
    style: str = "pop"

    @field_validator("time_signature")
    @classmethod
    def check_time_signature(cls, value: tuple[int, int]) -> tuple[int, int]:
        num, den = value
        if num < 1 or den not in _TIME_SIGNATURE_DENOMINATORS:
            raise ValueError("time_signature needs numerator >= 1 and denominator in (2, 4, 8, 16)")
        return value


class Section(BaseModel):
    name: str
    start_bar: int = Field(ge=0)
    bars: float = Field(gt=0)


class ChordSpan(BaseModel):
    bar: int = Field(ge=0)
    dur_bars: float = Field(gt=0)
    symbol: str


class Track(BaseModel):
    name: str = "track"
    program: int = Field(default=0, ge=0, le=127)
    role: TrackRole = "harmony"
    is_drum: bool = False
    notes: list[tuple[OnsetTick, int, int, Velocity]] = Field(default_factory=list)

    @property
    def end_tick(self) -> int:
        return max((n[0] + n[1] for n in self.notes), default=0)


class Composition(BaseModel):
    meta: Meta = Field(default_factory=Meta)
    structure: list[Section] = Field(default_factory=list)
    harmony: list[ChordSpan] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)

    @property
    def bar_ticks(self) -> int:
        num, den = self.meta.time_signature
        return int(PPQ * 4 * num / den)

    def total_bars(self) -> float:
        if not self.structure:
            return 0.0
        return max(s.start_bar + s.bars for s in self.structure)

    def piece_end_tick(self) -> int:
        structural = int(self.total_bars() * self.bar_ticks) if self.structure else 0
        played = max((t.end_tick for t in self.tracks), default=0)
        return max(structural, played)

    def clamp_to_boundary(self) -> Composition:
        """Truncate notes that extend beyond the piece boundary.

        Notes starting beyond the boundary are removed.
        Notes ending beyond the boundary have their duration truncated.
        """
        if not self.structure:
            return self
        limit = int(self.total_bars() * self.bar_ticks)
        new_tracks = []
        for track in self.tracks:
            clamped_notes = []
            for onset, dur, pitch, vel in track.notes:
                if onset >= limit:
                    continue
                end = onset + dur
                if end > limit:
                    dur = limit - onset
                if dur >= 1:
                    clamped_notes.append((onset, dur, pitch, vel))
            new_tracks.append(track.model_copy(update={"notes": clamped_notes}))
        return self.model_copy(update={"tracks": new_tracks})
