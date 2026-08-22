from __future__ import annotations

import re
from dataclasses import dataclass


class ChordParseError(ValueError):
    pass


@dataclass(frozen=True)
class ChordInfo:
    symbol: str
    root_pc: int
    pcs: frozenset[int]
    quality: str


_NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

_TEMPLATES: dict[str, tuple[str, tuple[int, ...]]] = {
    "": ("maj", (0, 4, 7)),
    "maj": ("maj", (0, 4, 7)),
    "m": ("min", (0, 3, 7)),
    "min": ("min", (0, 3, 7)),
    "7": ("dom7", (0, 4, 7, 10)),
    "maj7": ("maj7", (0, 4, 7, 11)),
    "m7": ("min7", (0, 3, 7, 10)),
    "m7b5": ("m7b5", (0, 3, 6, 10)),
    "dim": ("dim", (0, 3, 6)),
    "dim7": ("dim7", (0, 3, 6, 9)),
    "aug": ("aug", (0, 4, 8)),
    "6": ("maj6", (0, 4, 7, 9)),
    "m6": ("min6", (0, 3, 7, 9)),
    "add9": ("add9", (0, 2, 4, 7)),
    "sus4": ("sus4", (0, 5, 7)),
    "sus2": ("sus2", (0, 2, 7)),
    "5": ("power", (0, 7)),
}

_PATTERN = re.compile(r"^([A-Ga-g])([#b]?)(.*)$")


def parse_chord(symbol: str) -> ChordInfo:
    if not isinstance(symbol, str):
        raise ChordParseError(f"chord symbol must be str, got {type(symbol).__name__}")
    m = _PATTERN.match(symbol.strip())
    if not m:
        raise ChordParseError(f"cannot parse chord symbol: {symbol!r}")
    letter, accidental, rest = m.group(1), m.group(2), m.group(3)
    root = _NOTE_PC[letter.upper()]
    if accidental == "#":
        root = (root + 1) % 12
    elif accidental == "b":
        root = (root - 1) % 12
    if rest not in _TEMPLATES:
        raise ChordParseError(f"unknown chord quality {rest!r} in {symbol!r}")
    quality, intervals = _TEMPLATES[rest]
    pcs = frozenset((root + iv) % 12 for iv in intervals)
    return ChordInfo(symbol=symbol.strip(), root_pc=root, pcs=pcs, quality=quality)


def chord_root_degree(chord: ChordInfo, tonic_pc: int) -> int:
    return (chord.root_pc - tonic_pc) % 12
