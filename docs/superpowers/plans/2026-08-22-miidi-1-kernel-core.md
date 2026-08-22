# MiiDi Plan 1: Kernel Core (Schema + Music Utils + Renderer + Rule Evaluator)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python kernel: Composition schema with normalize/validate layers, music-theory utilities, deterministic MIDI rendering, and the six-axis rule evaluator with anti-degenerate gates producing `R_rule ∈ [0,100]`.

**Architecture:** Single installable package `src/miidi`. Data flows: raw dict → `normalize_raw()` → `Composition` → `validate_composition()` → `EvaluationContext` → axis functions → gates → `evaluate_rules()`. Zero LLM/network/RNG dependencies — bit-exact reproducible.

**Tech Stack:** Python ≥3.11, pydantic v2, midiutil; dev: pytest, mido.

**Spec:** `docs/superpowers/specs/2026-08-22-miidi-design.md` (§3 架构, §4 数据模型, §6.2 规则轨六轴, §6.3 反退化门)

## Global Constraints

- Python ≥3.11; pydantic v2 API only (`model_validate`, not v1 `parse_obj`).
- `PPQ = 480`; all onsets/durations are integer ticks.
- Evaluator path contains no randomness — same input, bit-exact same output.
- `normalize` never raises on bad input (returns errors list); `validate` never silently coerces (reports located violations).
- No comments in code unless citing a spec formula.
- Conventional commits, one commit per task. Run tests from repo root.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `env.example`, `.gitignore`, `src/miidi/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: installable package `miidi`; pytest wired to `tests/`.

- [ ] **Step 1: Write config files**

`pyproject.toml`:
```toml
[project]
name = "miidi"
version = "0.1.0"
description = "LLM symbolic music generation with dual-track evaluation"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.7", "midiutil>=1.2"]

[project.optional-dependencies]
dev = ["pytest>=8", "mido>=1.3"]
web = ["fastapi>=0.111", "uvicorn>=0.30"]
judge = ["httpx>=0.27"]
evaltools = ["numpy", "scipy", "pandas", "PyYAML"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`env.example`:
```
OPENAI_BASE_URL=https://api.example.com/v1
OPENAI_API_KEY=sk-your-key-here
MODEL_NAME=your-model-name
MIIDI_SOUNDFONT=/absolute/path/to/A320U.sf2
```

`.gitignore`:
```
__pycache__/
*.egg-info/
.env
.venv/
dist/
evals/results/runs/
node_modules/
webapp/frontend/dist/
output/
sessions/
```

`src/miidi/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/test_smoke.py`:
```python
import miidi


def test_package_imports():
    assert miidi.__version__
```

- [ ] **Step 2: Install and verify**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml env.example .gitignore src tests
git commit -m "chore: scaffold miidi package with pytest"
```

---

### Task 2: Chord symbol parser

**Files:**
- Create: `src/miidi/schema/__init__.py`, `src/miidi/schema/chords.py`
- Test: `tests/test_chords.py`

**Interfaces:**
- Produces:
  - `ChordInfo(symbol: str, root_pc: int, pcs: frozenset[int], quality: str)` frozen dataclass
  - `parse_chord(symbol: str) -> ChordInfo` raising `ChordParseError(ValueError)`
  - `chord_root_degree(chord: ChordInfo, tonic_pc: int) -> int` — root offset from tonic in semitones

- [ ] **Step 1: Write failing test**

`tests/test_chords.py`:
```python
import pytest

from miidi.schema.chords import ChordParseError, chord_root_degree, parse_chord


@pytest.mark.parametrize(
    "symbol,root,pcs",
    [
        ("C", 0, frozenset({0, 4, 7})),
        ("Am", 9, frozenset({9, 0, 4})),
        ("G7", 7, frozenset({7, 11, 2, 5})),
        ("Cmaj7", 0, frozenset({0, 4, 7, 11})),
        ("Dm7", 2, frozenset({2, 5, 9, 0})),
        ("Bdim", 11, frozenset({11, 2, 5})),
        ("Bm7b5", 11, frozenset({11, 2, 5, 9})),
        ("Cdim7", 0, frozenset({0, 3, 6, 9})),
        ("Caug", 0, frozenset({0, 4, 8})),
        ("Gsus4", 7, frozenset({7, 0, 2})),
        ("Asus2", 9, frozenset({9, 11, 4})),
        ("Cadd9", 0, frozenset({0, 2, 4, 7})),
        ("C6", 0, frozenset({0, 4, 7, 9})),
        ("Am6", 9, frozenset({9, 0, 4, 6})),
        ("F#m", 6, frozenset({6, 9, 1})),
        ("Bb", 10, frozenset({10, 2, 5})),
        ("Eb7", 3, frozenset({3, 7, 10, 1})),
        ("G5", 7, frozenset({7, 2})),
    ],
)
def test_parse_known_symbols(symbol, root, pcs):
    info = parse_chord(symbol)
    assert info.root_pc == root
    assert info.pcs == pcs


@pytest.mark.parametrize("symbol", ["H7", "xyz", "Cmaj9", "Fsus", "", "C##", "7"])
def test_invalid_symbols_raise(symbol):
    with pytest.raises(ChordParseError):
        parse_chord(symbol)


def test_case_insensitive_root():
    assert parse_chord("am").root_pc == 9


def test_root_degree():
    assert chord_root_degree(parse_chord("G"), 0) == 7
    assert chord_root_degree(parse_chord("F"), 0) == 5
    assert chord_root_degree(parse_chord("Em"), 9) == 7
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_chords.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement**

`src/miidi/schema/__init__.py`: empty file.

`src/miidi/schema/chords.py`:
```python
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
```

Note: `"Cmaj9"` must fail because regex `rest="maj9"` is not a template key. Verify ordering: longest suffixes are matched by exact string after root+accidental, so no ambiguity issues.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_chords.py -v`
Expected: PASS all

- [ ] **Step 5: Commit**

```bash
git add src/miidi/schema tests/test_chords.py
git commit -m "feat: chord symbol parser with 17 quality templates"
```

---

### Task 3: Composition pydantic models + scale utilities

**Files:**
- Create: `src/miidi/schema/model.py`, `src/miidi/musicutil/__init__.py`, `src/miidi/musicutil/scales.py`
- Test: `tests/test_model.py`, `tests/test_scales.py`

**Interfaces:**
- Produces:
  - `PPQ = 480` in `miidi.schema.model`
  - `KeySig(tonic_pc: int[0..11], mode: Literal["major","minor"])`
  - `Meta(title, bpm: int[20..300], time_signature: tuple[int,int], key: KeySig, style: str)`
  - `Section(name, start_bar: int≥0, bars: float>0)` / `ChordSpan(bar: int≥0, dur_bars: float>0, symbol: str)`
  - `Track(name, program: int[0..127], role ∈ {"melody","harmony","bass","counter","color","drums"}, is_drum: bool, notes: list[tuple[int,int,int,int]])` with `.end_tick` property
  - `Composition(meta, structure, harmony, tracks)` with `.bar_ticks` property, `.total_bars()`, `.piece_end_tick()`
  - `scale_pcs(key) -> frozenset[int]`; `MAJOR_PCS`, `NATURAL_MINOR_PCS`, `HARMONIC_MINOR_PCS` tuples

- [ ] **Step 1: Write failing tests**

`tests/test_model.py`:
```python
import pytest
from pydantic import ValidationError

from miidi.schema.model import Composition, KeySig, Meta, PPQ, Section, Track


def base_meta(**kw):
    return Meta(key=KeySig(tonic_pc=0), **kw)


def test_ppq_constant():
    assert PPQ == 480


def test_valid_composition():
    comp = Composition(
        meta=base_meta(),
        structure=[Section(name="A", start_bar=0, bars=4)],
        harmony=[{"bar": 0, "dur_bars": 1.0, "symbol": "C"}],
        tracks=[
            {"name": "Lead", "program": 73, "role": "melody",
             "notes": [[0, 240, 69, 96]]},
            {"name": "Drums", "role": "drums", "is_drum": True,
             "notes": [[0, 120, 36, 100]]},
        ],
    )
    assert comp.tracks[0].notes == [(0, 240, 69, 96)]
    assert comp.bar_ticks == 1920
    assert comp.total_bars() == 4.0
    assert comp.piece_end_tick() >= 1920


def test_note_tuple_constraints():
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(0, 240, 69)])
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(0, 240, 69, 200)])
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(-1, 240, 69, 96)])


def test_program_and_role_constrained():
    with pytest.raises(ValidationError):
        Track(name="x", program=128)
    with pytest.raises(ValidationError):
        Track(name="x", role="vocalist")


def test_bpm_bounds():
    with pytest.raises(ValidationError):
        base_meta(bpm=10)
    assert base_meta(bpm=300).bpm == 300
```

`tests/test_scales.py`:
```python
from miidi.musicutil.scales import (
    HARMONIC_MINOR_PCS, MAJOR_PCS, NATURAL_MINOR_PCS, scale_pcs,
)
from miidi.schema.model import KeySig


def test_major_scale():
    assert MAJOR_PCS == (0, 2, 4, 5, 7, 9, 11)
    assert scale_pcs(KeySig(tonic_pc=0, mode="major")) == frozenset(MAJOR_PCS)


def test_natural_minor_transposed():
    assert NATURAL_MINOR_PCS == (0, 2, 3, 5, 7, 8, 10)
    assert scale_pcs(KeySig(tonic_pc=9, mode="minor")) == frozenset(
        {(9 + x) % 12 for x in NATURAL_MINOR_PCS}
    )


def test_harmonic_minor_constant():
    assert HARMONIC_MINOR_PCS == (0, 2, 3, 5, 7, 8, 11)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_model.py tests/test_scales.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/schema/model.py`:
```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PPQ = 480

TrackRole = Literal["melody", "harmony", "bass", "counter", "color", "drums"]


class KeySig(BaseModel):
    tonic_pc: int = Field(ge=0, le=11)
    mode: Literal["major", "minor"] = "major"


class Meta(BaseModel):
    title: str = "untitled"
    bpm: int = Field(default=120, ge=20, le=300)
    time_signature: tuple[int, int] = (4, 4)
    key: KeySig = KeySig(tonic_pc=0)
    style: str = "pop"


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
    notes: list[tuple[int, int, int, int]] = Field(default_factory=list)

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
```

`src/miidi/musicutil/__init__.py`: empty file.

`src/miidi/musicutil/scales.py`:
```python
from __future__ import annotations

from miidi.schema.model import KeySig

MAJOR_PCS = (0, 2, 4, 5, 7, 9, 11)
NATURAL_MINOR_PCS = (0, 2, 3, 5, 7, 8, 10)
HARMONIC_MINOR_PCS = (0, 2, 3, 5, 7, 8, 11)


def scale_pcs(key: KeySig) -> frozenset[int]:
    steps = MAJOR_PCS if key.mode == "major" else NATURAL_MINOR_PCS
    return frozenset((key.tonic_pc + s) % 12 for s in steps)


def minor_superset_pcs(key: KeySig) -> frozenset[int]:
    return frozenset((key.tonic_pc + s) % 12 for s in (*NATURAL_MINOR_PCS, 11))
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_model.py tests/test_scales.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi tests
git commit -m "feat: composition models and scale utilities"
```

---

### Task 4: Normalizer

**Files:**
- Create: `src/miidi/schema/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: `Composition`, `Track`, `PPQ`.
- Produces:
  - `DEFAULT_VELOCITY = 96`
  - `NormalizeResult(composition: Composition | None, repairs: list[str], errors: list[str])`
  - `normalize_raw(data: object) -> NormalizeResult` — never raises.
  - Conversion rules (spec §4): 4-int arrays pass through after range check; dict notes `{pitch, duration, onset?, velocity?}` accepted; pitch `"C4"`/`60` both OK; string durations are note-values (`"1"`→1920, `"2"`→960, `"d2"`→1440, `"4"`→480, `"d4"`→720, `"8"`→240, `"16"`→120, `"32"`→60, `"T4"`→160, `"T8"`→80, `"d8"`→360), numeric durations are beats (`×PPQ`); missing onset → sequential cursor fill from track start; missing velocity → 96; `role=="drums"` implies `is_drum=True`; unknown duration/pitch → error entry (never silent default).
  - Unrepairable input → `composition=None`.

- [ ] **Step 1: Write failing test**

`tests/test_normalize.py`:
```python
from miidi.schema.normalize import normalize_raw


def clean(data):
    res = normalize_raw(data)
    assert res.errors == [], res.errors
    return res.composition


def test_canonical_arrays_passthrough():
    comp = clean({"tracks": [{"name": "L", "notes": [[0, 240, 69, 80]]}]})
    assert comp.tracks[0].notes == [(0, 240, 69, 80)]


def test_object_note_string_pitch_value_duration():
    comp = clean({"tracks": [{"name": "L", "notes": [
        {"pitch": "C4", "duration": "4"},
        {"pitch": "E4", "duration": "8"},
    ]}]})
    assert comp.tracks[0].notes[0] == (0, 480, 60, 96)
    assert comp.tracks[0].notes[1] == (480, 240, 64, 96)


def test_numeric_duration_is_beats():
    comp = clean({"tracks": [{"notes": [{"pitch": 60, "duration": 0.5, "velocity": 40}]}]})
    assert comp.tracks[0].notes == [(0, 240, 60, 40)]


def test_explicit_onset_respected_and_cursor_follows():
    comp = clean({"tracks": [{"notes": [
        {"pitch": 60, "duration": "4"},
        {"pitch": 62, "duration": "4", "onset": 960},
        {"pitch": 64, "duration": "4"},
    ]}]})
    onsets = [n[0] for n in comp.tracks[0].notes]
    assert onsets == [0, 960, 1440]


def test_string_pitch_variants():
    comp = clean({"tracks": [{"notes": [
        {"pitch": "F#5", "duration": "4"},
        {"pitch": "Bb3", "duration": "4"},
    ]}]})
    assert [n[2] for n in comp.tracks[0].notes] == [78, 58]


def test_drums_inferred_from_role():
    comp = clean({"tracks": [{"name": "D", "role": "drums",
                              "notes": [[0, 120, 36, 100]]}]})
    assert comp.tracks[0].is_drum is True


def test_bad_pitch_reported_not_fatal():
    res = normalize_raw({"tracks": [{"notes": [
        {"pitch": "Q4", "duration": "4"},
        {"pitch": "C4", "duration": "4"},
    ]}]})
    assert res.composition is not None
    assert len(res.composition.tracks[0].notes) == 1
    assert any("note[0]" in e for e in res.errors)


def test_unrepairable_returns_none():
    res = normalize_raw("not a dict")
    assert res.composition is None and res.errors


def test_empty_tracks_returns_none():
    res = normalize_raw({"tracks": []})
    assert res.composition is None


def test_unknown_duration_is_error_not_default():
    res = normalize_raw({"tracks": [{"notes": [{"pitch": 60, "duration": "?"}]}]})
    assert res.errors
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/schema/normalize.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from miidi.schema.model import Composition, PPQ


@dataclass
class NormalizeResult:
    composition: Composition | None
    repairs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_VALUE_DURATIONS = {
    "1": 1920, "2": 960, "d2": 1440, "4": 480, "d4": 720, "8": 240,
    "16": 120, "32": 60, "T4": 160, "T8": 80, "d8": 360,
}
DEFAULT_VELOCITY = 96


def _as_int(v: object) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _parse_pitch(value: object) -> int | None:
    iv = _as_int(value)
    if iv is not None:
        return iv if 0 <= iv <= 127 else None
    if isinstance(value, float) and value.is_integer() and 0 <= value <= 127:
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        letter = s[:1].upper()
        if letter not in _LETTERS:
            return None
        body = s[1:]
        acc = 0
        while body and body[0] in "#b":
            acc += 1 if body[0] == "#" else -1
            body = body[1:]
        try:
            octave = int(body)
        except ValueError:
            return None
        midi = (octave + 1) * 12 + (_LETTERS[letter] + acc) % 12
        return midi if 0 <= midi <= 127 else None
    return None


def _parse_duration(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value > 0:
            return max(1, round(value * PPQ))
        return None
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _VALUE_DURATIONS:
            return _VALUE_DURATIONS[s]
        try:
            beats = float(s)
        except ValueError:
            return None
        if beats > 0:
            return max(1, round(beats * PPQ))
    return None


def _coerce_note(raw: object, cursor: int) -> tuple[int, int, int, int] | None:
    if isinstance(raw, (list, tuple)):
        if len(raw) != 4:
            return None
        vals = []
        for v in raw:
            iv = _as_int(v)
            if iv is None:
                return None
            vals.append(iv)
        onset, dur, pitch, vel = vals
        if onset < 0 or dur < 1 or not 0 <= pitch <= 127 or not 1 <= vel <= 127:
            return None
        return (onset, dur, pitch, vel)
    if not isinstance(raw, dict):
        return None
    pitch = _parse_pitch(raw.get("pitch"))
    dur = _parse_duration(raw.get("duration"))
    if pitch is None or dur is None:
        return None
    onset = cursor
    if "onset" in raw:
        o = _as_int(raw.get("onset"))
        if o is None or o < 0:
            o2 = raw.get("onset")
            if isinstance(o2, (int, float)) and o2 >= 0:
                onset = int(o2)
            else:
                return None
        else:
            onset = o
    vel = DEFAULT_VELOCITY
    if "velocity" in raw:
        v = raw.get("velocity")
        vi = _as_int(v)
        if vi is None:
            if isinstance(v, (int, float)) and 1 <= v <= 127:
                vel = int(v)
            else:
                return None
        elif 1 <= vi <= 127:
            vel = vi
        else:
            return None
    return (onset, dur, pitch, vel)


def normalize_raw(data: object) -> NormalizeResult:
    repairs: list[str] = []
    errors: list[str] = []
    if not isinstance(data, dict):
        return NormalizeResult(None, repairs,
                               [f"top level must be an object, got {type(data).__name__}"])
    meta_in = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    raw_tracks = data.get("tracks")
    if not isinstance(raw_tracks, list) or not raw_tracks:
        return NormalizeResult(None, repairs, errors + ["no tracks found"])
    tracks = []
    for i, rt in enumerate(raw_tracks):
        if not isinstance(rt, dict):
            errors.append(f"track[{i}] is not an object; skipped")
            continue
        role = rt.get("role", "harmony")
        is_drum = bool(rt.get("is_drum", False)) or role == "drums"
        program = _as_int(rt.get("program", 0)) or 0
        if not 0 <= program <= 127:
            errors.append(f"track[{i}] program {program!r} out of range; coerced to 0")
            program = 0
        cursor = 0
        notes = []
        raw_notes = rt.get("notes", [])
        if not isinstance(raw_notes, list):
            errors.append(f"track[{i}] notes is not a list; skipped")
            continue
        for j, rn in enumerate(raw_notes):
            note = _coerce_note(rn, cursor)
            if note is None:
                errors.append(f"track[{i}] note[{j}] unparseable: {rn!r}")
                continue
            if isinstance(rn, dict):
                if "onset" not in rn:
                    repairs.append(f"track[{i}] note[{j}] onset filled at {cursor}")
                if "velocity" not in rn:
                    repairs.append(f"track[{i}] note[{j}] velocity defaulted")
            notes.append(note)
            cursor = note[0] + note[1]
        if notes:
            tracks.append({
                "name": str(rt.get("name", f"track{i}")),
                "program": program,
                "role": role,
                "is_drum": is_drum,
                "notes": notes,
            })
    if not tracks:
        return NormalizeResult(None, repairs, errors + ["no usable tracks"])
    structure = []
    raw_structure = data.get("structure", [])
    cursor_bar = 0
    if isinstance(raw_structure, list):
        for i, item in enumerate(raw_structure):
            if not isinstance(item, dict) or "bars" not in item:
                errors.append(f"structure[{i}] malformed; skipped")
                continue
            bars = item.get("bars")
            try:
                bars_f = float(bars)
            except (TypeError, ValueError):
                errors.append(f"structure[{i}] bars={bars!r}; skipped")
                continue
            if bars_f <= 0:
                errors.append(f"structure[{i}] bars={bars_f}; skipped")
                continue
            start = _as_int(item.get("start_bar"))
            if start is None:
                start = int(cursor_bar)
                if "start_bar" not in item:
                    repairs.append(f"structure[{i}] start_bar filled to {start}")
            if start < 0:
                errors.append(f"structure[{i}] negative start_bar; skipped")
                continue
            name = item.get("name", f"sec{i}")
            structure.append({"name": str(name), "start_bar": start, "bars": bars_f})
            cursor_bar = start + bars_f
    harmony = []
    raw_harmony = data.get("harmony", [])
    if isinstance(raw_harmony, list):
        for i, item in enumerate(raw_harmony):
            if not isinstance(item, dict):
                errors.append(f"harmony[{i}] not an object; skipped")
                continue
            bar = _as_int(item.get("bar"))
            symbol = item.get("symbol")
            try:
                dur_f = float(item.get("dur_bars", 1.0))
            except (TypeError, ValueError):
                errors.append(f"harmony[{i}] dur_bars invalid; skipped")
                continue
            if bar is None or bar < 0 or dur_f <= 0 or not isinstance(symbol, str):
                errors.append(f"harmony[{i}] malformed; skipped")
                continue
            harmony.append({"bar": bar, "dur_bars": dur_f, "symbol": symbol})
    payload = {"meta": meta_in, "structure": structure, "harmony": harmony, "tracks": tracks}
    try:
        comp = Composition.model_validate(payload)
    except ValidationError as exc:
        return NormalizeResult(None, repairs, errors + [f"validation failed: {exc.error_count()} errors"])
    return NormalizeResult(comp, repairs, errors)
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/schema/normalize.py tests/test_normalize.py
git commit -m "feat: lenient normalizer converting LLM output to Composition"
```

---
### Task 5: Validator

**Files:**
- Create: `src/miidi/schema/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Composition`.
- Produces:
  - `Violation(location: str, code: str, message: str)` frozen dataclass; codes: `OVERLAP, PITCH_RANGE, VELOCITY_RANGE, BOUNDS, DRUM_ROLE`
  - `validate_composition(comp) -> list[Violation]` — empty list = valid
  - Overlap rule (spec §4): within one non-drum track, partially overlapping spans are violations; identical `(onset,dur)` spans are chords and allowed.

- [ ] **Step 1: Write failing test**

`tests/test_validate.py`:
```python
from miidi.schema.model import Composition, Track
from miidi.schema.validate import validate_composition


def comp_with(track: Track) -> Composition:
    return Composition(tracks=[track])


def test_clean_passes_with_chord():
    c = comp_with(Track(name="L", notes=[(0, 240, 60, 96), (0, 240, 64, 96),
                                         (240, 240, 67, 96)]))
    assert validate_composition(c) == []


def test_partial_overlap_detected():
    c = comp_with(Track(name="L", notes=[(0, 480, 60, 96), (240, 480, 64, 96)]))
    vs = validate_composition(c)
    assert any(v.code == "OVERLAP" and "L" in v.location for v in vs)


def test_pitch_velocity_ranges():
    c = comp_with(Track(name="L", notes=[(0, 240, 128, 96), (240, 240, 60, 0)]))
    codes = {v.code for v in validate_composition(c)}
    assert codes == {"PITCH_RANGE", "VELOCITY_RANGE"}


def test_bounds_vs_structure():
    ok = Composition(
        structure=[{"name": "A", "start_bar": 0, "bars": 2}],
        tracks=[Track(name="L", notes=[(1920, 1920, 60, 96)])],
    )
    assert validate_composition(ok) == []
    bad = Composition(
        structure=[{"name": "A", "start_bar": 0, "bars": 1}],
        tracks=[Track(name="L", notes=[(1800, 480, 60, 96)])],
    )
    assert any(v.code == "BOUNDS" for v in validate_composition(bad))


def test_no_structure_uses_played_extent():
    assert validate_composition(comp_with(Track(name="L", notes=[(0, 960, 60, 96)]))) == []


def test_drum_role_consistency():
    c = comp_with(Track(name="D", role="melody", is_drum=True,
                        notes=[(0, 120, 38, 100)]))
    assert any(v.code == "DRUM_ROLE" for v in validate_composition(c))


def test_violation_location_specific():
    c = comp_with(Track(name="Bass", notes=[(0, 240, 200, 96)]))
    vs = validate_composition(c)
    assert vs[0].location == "Bass/note0"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_validate.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/schema/validate.py`:
```python
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
        bar = comp.bar_ticks
        limit = int(max(s.start_bar + s.bars for s in comp.structure) * bar)
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
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_validate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/schema/validate.py tests/test_validate.py
git commit -m "feat: hard validator with located violations"
```

---

### Task 6: Band primitive + GM tables + channels

**Files:**
- Create: `src/miidi/musicutil/band.py`, `src/miidi/musicutil/gm.py`
- Test: `tests/test_band.py`, `tests/test_gm.py`

**Interfaces:**
- Produces:
  - `band(x, lo0, lo1, hi1, hi0, floor=0.0) -> float` — trapezoid sweet-spot, plateau 1.0, floor outside (spec §6.3)
  - `norm_entropy(counts: list[int]) -> float ∈ [0,1]`
  - `play_comf(program: int) -> tuple[tuple[int,int], tuple[int,int]]` — ((PLAY),(COMF)) ranges for all 128 GM programs with family fallback; values per standard pedagogical tables (spec §1.2 借鉴 HYRA)
  - Drum constants: `KICK=36, SNARE=38, CLOSED_HAT=42, OPEN_HAT=46, RIDE=51, CRASH=49`
  - `assign_channels(is_drum_flags: list[bool]) -> list[int]` — melodic tracks get sequential channels skipping 9; drums pinned to 9; >15 melodic tracks raises ValueError

- [ ] **Step 1: Write failing tests**

`tests/test_band.py`:
```python
from miidi.musicutil.band import band, norm_entropy


def test_plateau_is_one():
    assert band(5, 0, 2, 8, 10) == 1.0


def test_ramps():
    assert band(0, 0, 2, 8, 10) == 0.0
    assert band(1, 0, 2, 8, 10) == 0.5
    assert band(10, 0, 2, 8, 10) == 0.0
    assert band(9, 0, 2, 8, 10) == 0.5


def test_floor_parameter():
    assert band(10, 0, 2, 8, 10, floor=0.4) == 0.4
    assert band(-1, 0, 2, 8, 10, floor=0.4) == 0.4


def test_entropy():
    assert norm_entropy([5]) == 0.0
    assert norm_entropy([]) == 0.0
    assert abs(norm_entropy([1, 1]) - 1.0) < 1e-9
    assert 0.0 < norm_entropy([3, 1]) < 1.0
```

`tests/test_gm.py`:
```python
import pytest

from miidi.musicutil.gm import (
    CLOSED_HAT, CRASH, KICK, OPEN_HAT, RIDE, SNARE, assign_channels, play_comf,
)


def test_drum_constants():
    assert (KICK, SNARE, CLOSED_HAT, OPEN_HAT, RIDE, CRASH) == (36, 38, 42, 46, 51, 49)


def test_all_128_covered_and_nested():
    for p in range(128):
        play, comf = play_comf(p)
        assert 0 <= play[0] < play[1] <= 127
        assert play[0] <= comf[0] and comf[1] <= play[1]


def test_known_values():
    assert play_comf(40)[0] == (55, 100)
    assert play_comf(0)[0] == (21, 108)
    assert play_comf(73)[0] == (59, 96)


def test_assign_channels_skips_9():
    chans = assign_channels([False] * 12)
    assert 9 not in chans and len(set(chans)) == 12


def test_drums_pin_to_nine():
    assert assign_channels([False, True, False]) == [0, 9, 1]


def test_too_many_melodic_tracks_raises():
    with pytest.raises(ValueError):
        assign_channels([False] * 16)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_band.py tests/test_gm.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/musicutil/band.py`:
```python
from __future__ import annotations

import math


def band(x: float, lo0: float, lo1: float, hi1: float, hi0: float,
         floor: float = 0.0) -> float:
    if x <= lo0:
        return floor
    if x < lo1:
        return floor + (1.0 - floor) * (x - lo0) / (lo1 - lo0)
    if x <= hi1:
        return 1.0
    if x < hi0:
        return floor + (1.0 - floor) * (hi0 - x) / (hi0 - hi1)
    return floor


def norm_entropy(counts: list[int]) -> float:
    tot = sum(counts)
    if tot <= 0 or len(counts) <= 1:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / tot
            h -= p * math.log(p)
    return h / math.log(len(counts))
```

`src/miidi/musicutil/gm.py`:
```python
from __future__ import annotations

KICK, SNARE, CLOSED_HAT, OPEN_HAT, RIDE, CRASH = 36, 38, 42, 46, 51, 49

_GENERIC = ((24, 100), (33, 91))

_GROUPS: list[tuple[range, tuple[tuple[int, int], tuple[int, int]]]] = [
    (range(0, 8), ((21, 108), (28, 100))),
    (range(16, 24), ((24, 100), (36, 91))),
    (range(24, 32), ((40, 88), (40, 79))),
    (range(32, 40), ((28, 67), (28, 55))),
    (range(48, 52), ((40, 96), (48, 88))),
    (range(80, 104), ((36, 96), (43, 88))),
]

_OVERRIDES: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    8: ((48, 96), (53, 89)), 9: ((60, 108), (64, 103)), 10: ((60, 96), (64, 91)),
    11: ((53, 89), (53, 84)), 12: ((45, 96), (48, 91)), 13: ((72, 108), (76, 103)),
    14: ((43, 79), (48, 74)), 15: ((53, 89), (57, 84)),
    40: ((55, 100), (55, 93)), 41: ((48, 88), (48, 81)), 42: ((36, 84), (36, 76)),
    43: ((28, 60), (28, 50)), 44: ((40, 96), (48, 88)), 45: ((40, 96), (48, 88)),
    46: ((24, 103), (28, 96)), 47: ((36, 81), (40, 76)),
    52: ((40, 84), (43, 79)), 53: ((40, 84), (43, 79)), 54: ((40, 84), (43, 79)),
    55: ((48, 88), (52, 81)),
    56: ((52, 84), (54, 79)), 57: ((40, 72), (40, 67)), 58: ((28, 58), (30, 53)),
    59: ((52, 82), (54, 77)), 60: ((35, 77), (41, 72)), 61: ((48, 84), (52, 79)),
    62: ((40, 88), (48, 81)), 63: ((40, 88), (48, 81)),
    64: ((49, 81), (52, 76)), 65: ((44, 76), (49, 72)), 66: ((40, 72), (44, 67)),
    67: ((34, 67), (37, 62)), 68: ((58, 91), (60, 86)), 69: ((52, 84), (55, 79)),
    70: ((34, 72), (36, 67)), 71: ((50, 91), (52, 84)),
    72: ((60, 96), (62, 91)), 73: ((59, 96), (62, 91)), 74: ((54, 91), (57, 86)),
    75: ((48, 79), (50, 74)), 76: ((48, 84), (52, 79)), 77: ((53, 84), (57, 79)),
    78: ((60, 91), (62, 86)), 79: ((60, 96), (64, 91)),
    104: ((48, 84), (52, 79)), 105: ((48, 84), (52, 79)), 106: ((48, 84), (52, 79)),
    107: ((48, 84), (52, 79)), 108: ((53, 89), (57, 84)), 109: ((48, 84), (52, 79)),
    110: ((55, 91), (55, 86)), 111: ((58, 89), (60, 84)),
    112: ((60, 91), (64, 86)), 113: ((48, 84), (52, 79)), 114: ((48, 84), (52, 79)),
    115: ((48, 84), (52, 79)), 116: ((40, 79), (43, 74)), 117: ((40, 79), (43, 74)),
    118: ((40, 84), (43, 79)), 119: ((48, 96), (52, 89)),
}


def _build() -> dict[int, tuple[tuple[int, int], tuple[int, int]]]:
    table: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
    for grp, val in _GROUPS:
        for p in grp:
            table[p] = val
    table.update({p: _GENERIC for p in range(120, 128)})
    table.update(_OVERRIDES)
    return {p: table[p] for p in range(128)}


_PROGRAM_TABLE = _build()


def play_comf(program: int) -> tuple[tuple[int, int], tuple[int, int]]:
    return _PROGRAM_TABLE[max(0, min(127, int(program)))]


def assign_channels(is_drum_flags: list[bool]) -> list[int]:
    channels: list[int] = []
    next_free = 0
    for is_drum in is_drum_flags:
        if is_drum:
            channels.append(9)
            continue
        if next_free == 9:
            next_free += 1
        if next_free > 15:
            raise ValueError("more than 15 melodic tracks cannot fit MIDI channels")
        channels.append(next_free)
        next_free += 1
    return channels
```

Note: `_GROUPS` + `_OVERRIDES` together must cover all 128 programs — `test_all_128_covered_and_nested` will KeyError-fail on any gap. If a gap surfaces at runtime, extend `_GROUPS` or `_OVERRIDES`; do not weaken the test.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_band.py tests/test_gm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/musicutil tests
git commit -m "feat: band primitive, GM ranges, channel assignment"
```

---

### Task 7: MIDI renderer + fail-soft WAV

**Files:**
- Create: `src/miidi/render/__init__.py`, `src/miidi/render/midi.py`, `src/miidi/render/audio.py`
- Test: `tests/test_render_midi.py`, `tests/test_render_audio.py`

**Interfaces:**
- Consumes: `Composition`, `assign_channels`, `PPQ`.
- Produces:
  - `generate_midi(comp: Composition, out_dir: Path) -> Path` — sanitized filename `<title>.mid`; tempo + time signature on track 0; drums on ch 9 without program change
  - `AudioUnavailableError(RuntimeError)`
  - `midi_to_wav(midi_path, wav_path=None, soundfont=None) -> Path` — raises `AudioUnavailableError` when fluidsynth or soundfont missing (fail-soft, spec §10)

- [ ] **Step 1: Write failing tests**

`tests/test_render_midi.py`:
```python
import mido

from miidi.render.midi import generate_midi
from miidi.schema.model import Composition


def sample_comp() -> Composition:
    return Composition(
        meta={"title": "Test Song", "bpm": 100},
        tracks=[
            {"name": "Lead", "program": 73, "role": "melody",
             "notes": [[0, 240, 69, 96], [240, 240, 71, 96]]},
            {"name": "Drums", "role": "drums", "is_drum": True,
             "notes": [[0, 120, 36, 100], [240, 120, 38, 100]]},
        ],
    )


def collect(path):
    mid = mido.MidiFile(path)
    notes, programs = [], []
    for track in mid.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                notes.append((msg.channel, msg.note, t))
            elif msg.type == "program_change":
                programs.append((msg.channel, msg.program))
    return notes, programs


def test_roundtrip(tmp_path):
    path = generate_midi(sample_comp(), tmp_path)
    notes, programs = collect(path)
    assert (0, 69, 0) in notes and (0, 71, 240) in notes
    assert (9, 36, 0) in notes and (9, 38, 240) in notes
    assert (0, 73) in programs


def test_tempo_written(tmp_path):
    path = generate_midi(sample_comp(), tmp_path)
    mid = mido.MidiFile(path)
    tempos = [m.tempo for tr in mid.tracks for m in tr if m.type == "set_tempo"]
    assert any(abs(t - mido.bpm2tempo(100)) < 2 for t in tempos)


def test_title_sanitized(tmp_path):
    comp = sample_comp().model_copy(deep=True)
    comp.meta.title = "a/b:c?"
    path = generate_midi(comp, tmp_path)
    assert "/" not in path.name and ":" not in path.name
```

`tests/test_render_audio.py`:
```python
import shutil

import pytest

from miidi.render.audio import AudioUnavailableError, midi_to_wav


def test_missing_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    fake = tmp_path / "x.mid"
    fake.write_bytes(b"MThd")
    with pytest.raises(AudioUnavailableError):
        midi_to_wav(fake, soundfont=tmp_path / "s.sf2")
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_render_midi.py tests/test_render_audio.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/render/__init__.py`: empty file.

`src/miidi/render/midi.py`:
```python
from __future__ import annotations

import math
import re
from pathlib import Path

from midiutil import MIDIFile

from miidi.musicutil.gm import assign_channels
from miidi.schema.model import PPQ, Composition


def generate_midi(comp: Composition, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", comp.meta.title).strip("_") or "untitled"
    path = out_dir / f"{safe}.mid"
    mf = MIDIFile(len(comp.tracks), deinterleave=False)
    channels = assign_channels([t.is_drum for t in comp.tracks])
    for ti, track in enumerate(comp.tracks):
        mf.addTrackName(ti, 0, track.name)
        if not track.is_drum:
            mf.addProgramChange(ti, channels[ti], 0, track.program)
        for onset, dur, pitch, vel in track.notes:
            mf.addNote(ti, channels[ti], pitch, onset / PPQ, dur / PPQ, vel)
    mf.addTempo(0, 0, comp.meta.bpm)
    num, den = comp.meta.time_signature
    if den in (2, 4, 8, 16):
        mf.addTimeSignature(0, 0, num, int(math.log2(den)), 24)
    with open(path, "wb") as fh:
        mf.writeFile(fh)
    return path
```

`src/miidi/render/audio.py`:
```python
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class AudioUnavailableError(RuntimeError):
    pass


def midi_to_wav(midi_path: Path, wav_path: Path | None = None,
                soundfont: Path | None = None) -> Path:
    binary = shutil.which("fluidsynth")
    sf = soundfont or os.environ.get("MIIDI_SOUNDFONT")
    if not binary:
        raise AudioUnavailableError("fluidsynth binary not found on PATH")
    if not sf or not Path(sf).is_file():
        raise AudioUnavailableError(f"soundfont not found: {sf!r}")
    wav_path = wav_path or midi_path.with_suffix(".wav")
    result = subprocess.run(
        [binary, "-ni", "-g", "1.0", "-F", str(wav_path), str(sf), str(midi_path)],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0 or not wav_path.exists():
        raise AudioUnavailableError(f"fluidsynth failed: {result.stderr.decode()[:400]}")
    return wav_path
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_render_midi.py tests/test_render_audio.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/render tests
git commit -m "feat: MIDI renderer and fail-soft WAV conversion"
```

---

### Task 8: Evaluation context + style defaults

**Files:**
- Create: `src/miidi/eval/__init__.py`, `src/miidi/eval/style.py`, `src/miidi/eval/context.py`
- Test: `tests/test_context.py`

**Interfaces:**
- Consumes: `Composition`, `parse_chord`, `scale_pcs`.
- Produces:
  - `StyleDefaults(bpm_range=(60.0,180.0), density_ref: dict[str,tuple[float,float]], swing_offsets: list[int], drum_patterns: dict[str,list[int]], section_vocab: dict[str,list[str]])` — later plans construct this from skill packs.
  - `NoteRef(track_index, track_name, role, onset, dur, pitch, velocity)` frozen dataclass with `.end`
  - `Vertical(pitch_classes: frozenset[int], pitches: list[int])`
  - `EvaluationContext.from_composition(comp, defaults=None)` with:
    - fields `comp, defaults, sections: list[(name,start_tick,end_tick)], piece_end`
    - properties `bar_ticks, key, scale`
    - `chord_at(tick) -> ChordInfo | None` (None when no span or unparseable symbol)
    - `sounding_at(tick, exclude_drum=True) -> list[NoteRef]`
    - `iterate_verticals(step=240)` yielding `(tick, Vertical)`
    - `track_of_role(role)`, `section_of_tick(tick)`
    - internal cached `_flat_notes(exclude_drum)` reused by axes

- [ ] **Step 1: Write failing test**

`tests/test_context.py`:
```python
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def comp() -> Composition:
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=[{"name": "verse", "start_bar": 0, "bars": 2},
                   {"name": "chorus", "start_bar": 2, "bars": 2}],
        harmony=[{"bar": 0, "dur_bars": 2.0, "symbol": "C"},
                 {"bar": 2, "dur_bars": 2.0, "symbol": "G"}],
        tracks=[
            {"name": "Mel", "role": "melody", "program": 73,
             "notes": [[0, 960, 72, 96], [960, 960, 74, 96]]},
            {"name": "Bas", "role": "bass", "program": 33,
             "notes": [[0, 1920, 36, 96], [1920, 1920, 43, 96]]},
        ],
    )


def test_sections_resolved_to_ticks():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.sections == [("verse", 0, 3840), ("chorus", 3840, 7680)]
    assert ctx.section_of_tick(4000) == 1
    assert ctx.piece_end == 7680


def test_chord_lookup():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.chord_at(100).root_pc == 0
    assert ctx.chord_at(4000).root_pc == 7


def test_sounding_excludes_drums_optionally():
    c2 = comp()
    from miidi.schema.model import Track
    c2.tracks.append(Track(name="Dr", role="drums", is_drum=True,
                           notes=[(0, 1920, 36, 100)]))
    ctx = EvaluationContext.from_composition(c2, StyleDefaults())
    assert len(ctx.sounding_at(0)) == 2
    assert len(ctx.sounding_at(0, exclude_drum=False)) == 3


def test_verticals_sampled_sorted():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    pairs = list(ctx.iterate_verticals())
    ticks = [t for t, _ in pairs]
    assert ticks[0] == 0 and all(b > a for a, b in zip(ticks, ticks[1:]))
    v0 = pairs[0][1]
    assert set(v0.pitch_classes) == {0}   # melody C + bass C


def test_roles_found():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.track_of_role("melody").name == "Mel"
    assert ctx.track_of_role("drums") is None


def test_empty_structure_single_section():
    bare = Composition(tracks=[{"name": "M", "role": "melody",
                                "notes": [[0, 480, 60, 96]]}])
    ctx = EvaluationContext.from_composition(bare, StyleDefaults())
    assert ctx.sections == [("all", 0, 1920)]   # nominal single bar minimum
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_context.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/eval/__init__.py`: empty file.

`src/miidi/eval/style.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StyleDefaults:
    bpm_range: tuple[float, float] = (60.0, 180.0)
    density_ref: dict[str, tuple[float, float]] = field(default_factory=dict)
    swing_offsets: list[int] = field(default_factory=list)
    drum_patterns: dict[str, list[int]] = field(default_factory=dict)
    section_vocab: dict[str, list[str]] = field(default_factory=lambda: {
        "chorus": ["chorus", "refrain", "hook"],
        "verse": ["verse", "couplet", "a"],
        "bridge": ["bridge", "b"],
        "intro": ["intro"],
        "outro": ["outro", "coda"],
    })
```

`src/miidi/eval/context.py`:
```python
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
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval tests/test_context.py
git commit -m "feat: evaluation context with sustain-aware verticals"
```

---
### Task 9: Axes — format (A1) + harmony (A2)

**Files:**
- Create: `src/miidi/eval/axes.py`
- Test: `tests/test_axes_harmony.py`

**Interfaces:**
- Consumes: `EvaluationContext`, `validate_composition`, `band`, `minor_superset_pcs`.
- Produces:
  - `AxisResult(score: float, details: dict)` dataclass
  - `axis_format(comp: Composition) -> tuple[float, list[Violation]]` — 1.0 when no violations else 0.0 (qualification gate; spec §6.2 A1)
  - `axis_harmony(ctx) -> AxisResult` with details keys `scale_adherence, chord_support, declaration_match, cluster_rate, cadence_rate`; inner weights 0.30/0.30/0.15/0.15/0.10
  - Semantics (spec §6.2 A2): scale adherence counts off-scale non-drum notes, exempting weak-position onsets (`onset % 240 != 0`) up to 15% of all notes; chord support = per-bar duration-mass chord-tone fraction over roles {bass,harmony,color,counter}, banded via `band(mean, 0.5, 0.8, 1.01, 1.01, floor=0.3)`; declaration match = mean over parsed-chord bars of `|sounding_pcs ∩ chord_pcs| / |chord_pcs|` (neutral 0.7 when no bars); cluster_rate = fraction of sampled verticals whose min adjacent semitone ≤ 1; cadence = fraction of section ends where chord one bar before end has degree 7 or 5 and final chord is degree 0 (neutral 0.7 when nothing parseable)

- [ ] **Step 1: Write failing test**

`tests/test_axes_harmony.py`:
```python
from miidi.eval.axes import axis_format, axis_harmony
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def build(harmony_symbols=("C", "F", "G", "C"), melody=(72, 74, 76, 72),
          extra_pad_notes=(), structure=None):
    pad = []
    for bar, pcs in enumerate([(60, 64, 67), (60, 65, 69), (59, 62, 67), (60, 64, 67)]):
        onset = bar * 1920
        pad += [(onset, 1920, p, 80) for p in pcs]
    pad += tuple(extra_pad_notes)
    bass = [(bar * 1920, 1920, root, 96)
            for bar, root in enumerate([36, 41, 43, 36])]
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=structure or [{"name": "A", "start_bar": 0, "bars": 4}],
        harmony=[{"bar": b, "dur_bars": 1.0, "symbol": s}
                 for b, s in enumerate(harmony_symbols)],
        tracks=[
            {"name": "Mel", "role": "melody", "program": 73,
             "notes": [(b * 1920, 1920, p, 96) for b, p in enumerate(melody)]},
            {"name": "Pad", "role": "harmony", "program": 0, "notes": pad},
            {"name": "Bs", "role": "bass", "program": 33, "notes": bass},
        ],
    )


def ctx_of(comp) -> EvaluationContext:
    return EvaluationContext.from_composition(comp, StyleDefaults())


def test_axis_format_gate():
    good = build()
    assert axis_format(good) == (1.0, [])
    bad = good.model_copy(deep=True)
    bad.tracks[0].notes.append((100, 480, 60, 96))
    score, viols = axis_format(bad)
    assert score == 0.0 and viols


def test_good_progression_high_score():
    res = axis_harmony(ctx_of(build()))
    assert res.details["scale_adherence"] == 1.0
    assert res.details["chord_support"] == 1.0
    assert res.details["declaration_match"] == 1.0
    assert res.details["cluster_rate"] == 0.0
    assert res.details["cadence_rate"] == 1.0
    assert res.score >= 0.85


def test_offkey_note_lowers_adherence_and_score():
    good_comp, good = build(), None
    good = axis_harmony(ctx_of(good_comp))
    bad_comp = good_comp.model_copy(deep=True)
    mel = list(bad_comp.tracks[0].notes)
    mel[2] = (3840, 1920, 66, 96)          # F#4 against C major
    bad_comp.tracks[0].notes = mel
    bad = axis_harmony(ctx_of(bad_comp))
    assert bad.details["scale_adherence"] < good.details["scale_adherence"]
    assert bad.score < good.score


def test_cluster_penalizes():
    good = axis_harmony(ctx_of(build()))
    clashing = build(extra_pad_notes=((0, 1920, 61, 80),))   # C + C#
    bad = axis_harmony(ctx_of(clashing))
    assert bad.details["cluster_rate"] > 0.0
    assert bad.score < good.score


def test_declaration_mismatch_detected():
    plain = axis_harmony(ctx_of(build()))
    mismatched = build(harmony_symbols=("Cmaj7", "F", "G", "C"))
    bad = axis_harmony(ctx_of(mismatched))
    assert bad.details["declaration_match"] < plain.details["declaration_match"]
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_axes_harmony.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

Create `src/miidi/eval/axes.py`:
```python
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
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_axes_harmony.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/axes.py tests/test_axes_harmony.py
git commit -m "feat: format gate and harmony axis"
```

---

### Task 10: Axes — voice writing (A3) + rhythm (A4)

**Files:**
- Modify: `src/miidi/eval/axes.py` (append functions)
- Test: `tests/test_axes_voice_rhythm.py`

**Interfaces:**
- Produces:
  - `axis_voice(ctx) -> AxisResult`, details `range_fit, parallel_count, leap_rate, register_gap`; inner weights 0.40/0.25/0.20/0.15; parallels component `1 - min(count,3)/3`; leap component `declining(rate, 0.10, 0.40)`; register gap band `(gap, 8, 14, 48, 60, floor=0.4)`, neutral 0.8 if either role missing
  - `axis_rhythm(ctx) -> AxisResult`, details `grid_adherence, density_fit, drum_pattern_fit, swing_consistency`; weights 0.30/0.30/0.25/0.15; neutral 1.0 for components without applicable data
  - Grid legality: onset legal iff ∃k∈{1,2,3,4,6,8,12}: (onset·k)%480==0, or onset%480 ∈ defaults.swing_offsets

- [ ] **Step 1: Write failing test**

`tests/test_axes_voice_rhythm.py`:
```python
from miidi.eval.axes import axis_rhythm, axis_voice
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition

MELODY_PITCHES = [74, 76, 77, 79, 77, 76, 74, 72,
                  74, 76, 77, 74, 72, 74, 76, 72]


def good_tracks():
    return [
        {"name": "Mel", "role": "melody", "program": 73,
         "notes": [(i * 480, 480, p, 96) for i, p in enumerate(MELODY_PITCHES)]},
        {"name": "Bs", "role": "bass", "program": 33,
         "notes": [(i * 960, 960, p, 96)
                   for i, p in enumerate([43, 45, 47, 43, 41, 43, 45, 43])]},
    ]


def ctx_of(tracks, style="pop", defaults=None) -> EvaluationContext:
    comp = Composition(meta={"style": style},
                       structure=[{"name": "A", "start_bar": 0, "bars": 4}],
                       tracks=tracks)
    return EvaluationContext.from_composition(comp, defaults or StyleDefaults())


def test_voice_baseline_high():
    res = axis_voice(ctx_of(good_tracks()))
    assert res.details["parallel_count"] == 0
    assert res.details["range_fit"] == 1.0
    assert res.details["leap_rate"] == 0.0
    assert res.score >= 0.85


def test_out_of_range_note_penalized():
    tracks = good_tracks()
    mel = list(tracks[0]["notes"])
    mel[0] = (0, 480, 110, 96)
    tracks[0]["notes"] = mel
    res = axis_voice(ctx_of(tracks))
    assert res.details["range_fit"] < 0.95
    assert res.score < axis_voice(ctx_of(good_tracks())).score


def test_parallel_fifths_counted():
    tracks = [
        {"name": "Top", "role": "harmony", "program": 0,
         "notes": [(0, 960, 67, 96), (960, 960, 69, 96)]},
        {"name": "Bot", "role": "bass", "program": 33,
         "notes": [(0, 960, 48, 96), (960, 960, 50, 96)]},
    ]
    res = axis_voice(ctx_of(tracks))
    assert res.details["parallel_count"] >= 1


def test_leaps_penalized():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 480, 60, 96), (480, 480, 96, 96),
                  (960, 480, 60, 96), (1440, 480, 96, 96)],
    }]
    res = axis_voice(ctx_of(tracks))
    assert res.details["leap_rate"] == 1.0
    assert res.score < axis_voice(ctx_of(good_tracks())).score


def test_rhythm_grid_clean():
    res = axis_rhythm(ctx_of(good_tracks()))
    assert res.details["grid_adherence"] == 1.0
    assert res.score >= 0.8


def test_offgrid_penalized():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 480, 72, 96), (483, 480, 74, 96)],
    }]
    res = axis_rhythm(ctx_of(tracks, style="classical"))
    assert res.details["grid_adherence"] < 1.0


def test_swing_whitelist_restores_adherence():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 220, 72, 96), (220, 260, 74, 96),
                  (480, 220, 76, 96), (700, 260, 77, 96)],
    }]
    defaults = StyleDefaults(swing_offsets=[220, 260, 700, 740])
    res = axis_rhythm(ctx_of(tracks, style="jazz", defaults=defaults))
    assert res.details["grid_adherence"] == 1.0


def test_drum_pattern_match():
    hits = [(0, 36), (960, 38), (240, 42), (720, 42), (1200, 42), (1680, 42)]
    tracks = [{
        "name": "Dr", "role": "drums", "is_drum": True,
        "notes": [(b * 1920 + r, 120, p, 100)
                  for b in range(4) for r, p in hits],
    }]
    defaults = StyleDefaults(drum_patterns={"kick": [0], "snare": [960],
                                            "hat": [240, 720, 1200, 1680]})
    res = axis_rhythm(ctx_of(tracks, style="lofi", defaults=defaults))
    assert res.details["drum_pattern_fit"] >= 0.95
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_axes_voice_rhythm.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

Append to `src/miidi/eval/axes.py`:
```python
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
        play_fracs.append(sum(1 for n in t.notes
                              if play_rng[0] <= n[2] <= play_rng[1]) / len(t.notes))
        comf_fracs.append(sum(1 for n in t.notes
                              if comf_rng[0] <= n[2] <= comf_rng[1]) / len(t.notes))
        seq = sorted(t.notes, key=lambda n: n[0])
        for a, b in zip(seq, seq[1:]):
            if b[0] >= a[0] + a[1]:
                steps += 1
                if abs(b[2] - a[2]) > 12:
                    leaps += 1
        bucket = "melody" if t.role in ("melody", "counter") else t.role
        role_means[bucket] = _mean([n[2] for n in t.notes])
    range_fit = 0.6 * (sum(play_fracs) / len(play_fracs) if play_fracs else 1.0) \
        + 0.4 * (sum(comf_fracs) / len(comf_fracs) if comf_fracs else 1.0)
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
    score = (0.40 * range_fit + 0.25 * par_component
             + 0.20 * leap_component + 0.15 * gap_component)
    return AxisResult(score=max(0.0, min(1.0, score)), details={
        "range_fit": range_fit,
        "parallel_count": parallels,
        "leap_rate": leap_rate,
        "register_gap": gap_component,
    })
```

Append:
```python
_DRUM_PITCH_BY_NAME = {"kick": 36, "snare": 38, "hat": 42}


def axis_rhythm(ctx: EvaluationContext) -> AxisResult:
    swing = set(ctx.defaults.swing_offsets)
    onsets = [n[0] for t in ctx.comp.tracks for n in t.notes]
    if onsets:
        legal = sum(1 for o in onsets
                    if any((o * k) % 480 == 0 for k in _GRID_KS) or o % 480 in swing)
        grid = legal / len(onsets)
    else:
        grid = 1.0

    bar = ctx.bar_ticks
    dens_components: list[float] = []
    for t in ctx.comp.tracks:
        ref = ctx.defaults.density_ref.get(t.role)
        if ref is None or not t.notes:
            continue
        span_bars = max(1, round((t.end_tick / bar)))
        per_bar = len(t.notes) / span_bars
        dens_components.append(band(per_bar, ref[0], ref[0] * 1.25,
                                    ref[1] * 0.8, ref[1], floor=0.3))
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

    offbeat = sorted(o % 480 for o in onsets
                     if not any((o * k) % 480 == 0 for k in _GRID_KS))
    if len(offbeat) >= 4:
        spread = max(offbeat) - min(offbeat)
        swing_consistency = 1.0 - min(spread / 120, 1.0) * 0.8
    else:
        swing_consistency = 1.0

    score = (0.30 * grid + 0.30 * density + 0.25 * drum_fit
             + 0.15 * swing_consistency)
    return AxisResult(score=max(0.0, min(1.0, score)), details={
        "grid_adherence": grid,
        "density_fit": density,
        "drum_pattern_fit": drum_fit,
        "swing_consistency": swing_consistency,
    })
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_axes_voice_rhythm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/axes.py tests/test_axes_voice_rhythm.py
git commit -m "feat: voice-writing and rhythm axes"
```

---

### Task 11: Axes — structure (A5) + dynamics (A6)

**Files:**
- Modify: `src/miidi/eval/axes.py` (append functions)
- Test: `tests/test_axes_structure_dynamics.py`

**Interfaces:**
- Produces:
  - `axis_structure(ctx) -> AxisResult`, details `coverage, repeat_family_sim, contrast_family_sim, contour_shape, motif_recall`; weights 0.25/0.25/0.25/0.15/0.10; neutral 0.8 for motif_recall when fewer than 2 sections or no melody
  - Family normalization: section family = name lowercased with trailing digits stripped (`verse2` → `verse`)
  - Per-section feature vector: 12-bin duration-weighted PC histogram + notes-per-bar + mean velocity → cosine similarity
  - Same-family pairs scored by `band(sim, 0.55, 0.70, 1.01, 1.01, floor=0.2)`; different-family pairs by `band(sim, 0.90, 0.95, 1.01, 1.01, floor=0.0)` inverted → use `1 - band(sim, ...)` so sim ≥0.95 scores 0
  - `axis_dynamics(ctx) -> AxisResult`, details `velocity_spread, gradient_ok`; weights 0.6 σ-band `band(σ, 4, 8, 45, 60, floor=0.1)` + 0.4 section-gradient (chorus-family mean velocity ≥ verse-family − 5 → 1.0; neutral 0.8 when either family absent)

- [ ] **Step 1: Write failing test**

`tests/test_axes_structure_dynamics.py`:
```python
from miidi.eval.axes import axis_dynamics, axis_structure
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def two_section_comp(sec_names, second_shift=0, velocities=None):
    vels = velocities or ([84] * 8 + [84] * 8)
    half_a = [(i * 240, 240, p, vels[i]) for i, p in
              enumerate([72, 74, 76, 74, 72, 74, 76, 79])]
    half_b = [((8 + i) * 240, 240, p + second_shift, vels[8 + i]) for i, p in
              enumerate([72, 74, 76, 74, 72, 74, 76, 79])]
    return Composition(
        meta={},
        structure=[{"name": sec_names[0], "start_bar": 0, "bars": 1},
                   {"name": sec_names[1], "start_bar": 1, "bars": 1}],
        tracks=[{"name": "M", "role": "melody", "program": 73,
                 "notes": half_a + half_b}],
    )


def ctx_of(comp) -> EvaluationContext:
    return EvaluationContext.from_composition(comp, StyleDefaults())


def test_coverage_full():
    res = axis_structure(ctx_of(two_section_comp(("verse", "verse2"))))
    assert res.details["coverage"] == 1.0


def test_repeat_family_similarity_high():
    res = axis_structure(ctx_of(two_section_comp(("verse", "verse2"))))
    assert res.details["repeat_family_sim"] >= 0.99


def test_contrast_family_low_sim_rewarded():
    same = axis_structure(ctx_of(two_section_comp(("verse", "chorus"))))
    contrast = axis_structure(
        ctx_of(two_section_comp(("verse", "chorus"), second_shift=5)))
    assert contrast.details["contrast_family_sim"] < same.details["contrast_family_sim"]
    assert contrast.score > same.score


def test_gap_in_structure_penalized():
    comp = two_section_comp(("verse", "chorus"))
    comp.structure[1].start_bar = 2          # leaves a 1-bar hole
    res = axis_structure(ctx_of(comp))
    assert res.details["coverage"] < 1.0


def test_constant_velocity_scores_low():
    comp = two_section_comp(("verse", "chorus"))
    res = axis_dynamics(ctx_of(comp))
    assert res.score <= 0.5


def test_gradient_velocity_scores_higher():
    flat = axis_dynamics(ctx_of(two_section_comp(("verse", "chorus"))))
    shaped = axis_dynamics(ctx_of(
        two_section_comp(("verse", "chorus"),
                         velocities=[82, 84, 86, 84, 82, 84, 86, 88,
                                     104, 108, 112, 108, 104, 108, 112, 116])))
    assert shaped.score > flat.score
    assert shaped.details["gradient_ok"] == 1.0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_axes_structure_dynamics.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

Append to `src/miidi/eval/axes.py`:
```python
import math as _math
import re as _re


def _family(name: str) -> str:
    return _re.sub(r"\d+$", "", name.strip().lower()) or name.strip().lower()


def _section_vectors(ctx: EvaluationContext) -> list[dict]:
    vectors = []
    for si, (name, start, end) in enumerate(ctx.sections):
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
    sims: dict[tuple[str, str], float] = {}
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            fa, fb = _family(vecs[i]["name"]), _family(vecs[j]["name"])
            va = vecs[i]["hist"] + [vecs[i]["density"] / 16.0, vecs[i]["vel"] / 128.0]
            vb = vecs[j]["hist"] + [vecs[j]["density"] / 16.0, vecs[j]["vel"] / 128.0]
            sims[(fa, fb)] = _cosine(va, vb)
    repeat_vals = [s for (fa, fb), s in sims.items() if fa == fb]
    contrast_vals = [s for (fa, fb), s in sims.items() if fa != fb]
    repeat_sim = _mean(repeat_vals) if repeat_vals else None
    contrast_sim = _mean(contrast_vals) if contrast_vals else None
    repeat_component = band(repeat_sim, 0.55, 0.70, 1.01, 1.01, floor=0.2) \
        if repeat_sim is not None else 0.8
    contrast_component = (1.0 - band(contrast_sim, 0.90, 0.95, 1.01, 1.01, floor=0.0)) \
        if contrast_sim is not None else 0.8

    densities = [v["density"] for v in vecs]
    shape = band(_std(densities), 0.3, 0.8, 8.0, 12.0, floor=0.2) \
        if len(densities) >= 2 else 0.8

    melody = ctx.track_of_role("melody")
    recall = 0.8
    if melody and len(ctx.sections) >= 2 and len(melody.notes) >= 4:
        first = [n for n in sorted(melody.notes, key=lambda n: n[0])
                 if ctx.section_of_tick(n[0]) == 0]
        rest = [n for n in sorted(melody.notes, key=lambda n: n[0])
                if ctx.section_of_tick(n[0]) > 0]
        if len(first) >= 4 and rest:
            target = _contour(first[:8])
            found = any(_has_contour(rest[i:i + 8], target)
                        for i in range(max(len(rest) - 7, 0))) if len(target) >= 2 else False
            recall = 1.0 if found else 0.3

    score = (0.25 * coverage_component + 0.25 * repeat_component
             + 0.25 * contrast_component + 0.15 * shape + 0.10 * recall)
    return AxisResult(score=max(0.0, min(1.0, score)), details={
        "coverage": coverage_component,
        "repeat_family_sim": repeat_sim if repeat_sim is not None else -1.0,
        "contrast_family_sim": contrast_sim if contrast_sim is not None else -1.0,
        "contour_shape": shape,
        "motif_recall": recall,
    })


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


def axis_dynamics(ctx: EvaluationContext) -> AxisResult:
    vels = [float(n.velocity) for n in ctx.flat_notes()]
    sigma = _std(vels)
    spread_component = band(sigma, 4, 8, 45, 60, floor=0.1)

    chorus_vels = [v["vel"] for v in _section_vectors(ctx)
                   if _family(v["name"]) in _CHORUS]
    verse_vels = [v["vel"] for v in _section_vectors(ctx)
                  if _family(v["name"]) in _VERSE]
    if chorus_vels and verse_vels:
        diff = _mean(chorus_vels) - _mean(verse_vels)
        gradient = band(diff, -5.0, 0.0, 60.0, 61.0, floor=0.2)
    else:
        gradient = 0.8

    score = 0.6 * spread_component + 0.4 * gradient
    return AxisResult(score=max(0.0, min(1.0, score)), details={
        "velocity_spread": spread_component,
        "gradient_ok": gradient,
    })
```

Note `_section_vectors` is called twice in dynamics — acceptable at this scale; cache later only if profiling demands.

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_axes_structure_dynamics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/axes.py tests/test_axes_structure_dynamics.py
git commit -m "feat: structure-development and dynamics axes"
```

---
### Task 12: Anti-degenerate gates

**Files:**
- Create: `src/miidi/eval/gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: `EvaluationContext`, `declining`, `band`.
- Produces (all return plain floats in [floor..1.0]; 1.0 = no penalty):
  - `gate_repetition(ctx) -> float` — per non-drum track, sliding 4-gram duplication ratio over tokens `(pitch, dur, gap_from_prev_end)`; gate = `declining(max_ratio, 0.30, 0.90)`; tracks with <8 notes ignored; empty → 1.0
  - `gate_density(ctx) -> float` — piece notes-per-bar vs `defaults.density_ref.get("__global__", (2.0, 30.0))` via `band(npb, lo, lo*1.25, hi*0.8, hi, floor=0.5)`
  - `gate_balance(ctx) -> float` — min duration-mass share across non-empty non-drum tracks via `band(smin, 0.05, 0.10, 1.01, 1.01, floor=0.4)`; single-track or none → 1.0
  - `gate_spread(ctx) -> float` — p95−p5 pitch spread before vs after trimming 3 highest + 3 lowest notes; ratio <0.6 (fake spread) → 0.6 else 1.0; <8 distinct pitches → 1.0

- [ ] **Step 1: Write failing test**

`tests/test_gates.py`:
```python
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.eval.gates import gate_balance, gate_density, gate_repetition, gate_spread
from miidi.schema.model import Composition


def ctx_of(tracks, defaults=None) -> EvaluationContext:
    comp = Composition(meta={},
                       structure=[{"name": "A", "start_bar": 0, "bars": 4}],
                       tracks=tracks)
    return EvaluationContext.from_composition(comp, defaults or StyleDefaults())


VARIED = [(i * 480, 480, p, 96) for i, p in
          enumerate([74, 76, 77, 79, 77, 76, 74, 72,
                     74, 76, 77, 74, 72, 74, 76, 72])]


def test_repetition_clean_track():
    assert gate_repetition(ctx_of([{"name": "M", "role": "melody",
                                    "program": 73, "notes": VARIED}])) >= 0.95


def test_repetition_copy_paste_penalized():
    looped = [(i * 480, 480, p, 96) for i, p in enumerate([74, 76, 77, 79] * 8)]
    assert gate_repetition(ctx_of([{"name": "M", "role": "melody",
                                    "program": 73, "notes": looped}])) <= 0.5


def test_density_extremes():
    normal = ctx_of([{"name": "M", "role": "melody", "program": 73, "notes": VARIED}])
    stuffed = [{"name": "M", "role": "melody", "program": 73,
                "notes": [(i * 60, 60, 60 + (i % 5), 96) for i in range(512)]}]
    assert gate_density(normal) == 1.0
    assert gate_density(ctx_of(stuffed)) <= 0.6


def test_balance_stub_track_penalized():
    tracks = [
        {"name": "A", "role": "harmony", "program": 0,
         "notes": [(b * 1920, 1920, p, 80) for b, p in
                   enumerate([60, 62, 64, 65])]},
        {"name": "B", "role": "harmony", "program": 0,
         "notes": [(b * 1920, 1920, p, 80) for b, p in
                   enumerate([67, 69, 71, 72])]},
        {"name": "Stub", "role": "color", "program": 73,
         "notes": [(0, 120, 90, 80)]},
    ]
    balanced = tracks[:2]
    assert gate_balance(ctx_of(balanced)) == 1.0
    assert gate_balance(ctx_of(tracks)) <= 0.7


def test_spread_real_vs_fake():
    real = ctx_of([{"name": "M", "role": "melody", "program": 0,
                    "notes": [(i * 240, 240, 48 + ((i * 7) % 37), 96)
                              for i in range(32)]}])
    fake_notes = list(VARIED) + [(7680, 480, 127, 96), (8160, 480, 126, 96),
                                 (8640, 480, 125, 96)]
    fake = ctx_of([{"name": "M", "role": "melody", "program": 0,
                    "notes": fake_notes}])
    assert gate_spread(real) > gate_spread(fake)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_gates.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/eval/gates.py`:
```python
from __future__ import annotations

from miidi.eval.axes import declining
from miidi.eval.context import EvaluationContext
from miidi.musicutil.band import band


def _grams_ratio(track) -> float:
    seq = sorted(track.notes, key=lambda n: n[0])
    tokens = []
    for a, b in zip(seq, seq[1:]):
        gap = b[0] - (a[0] + a[1])
        tokens.append((a[2], a[1], gap))
    if len(tokens) < 4:
        return 0.0
    grams = [tuple(tokens[i:i + 4]) for i in range(len(tokens) - 3)]
    return (len(grams) - len(set(grams))) / len(grams)


def gate_repetition(ctx: EvaluationContext) -> float:
    ratios = [_grams_ratio(t) for t in ctx.comp.tracks
              if not t.is_drum and len(t.notes) >= 8]
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
    if len(masses) < 2:
        return 1.0
    total = sum(masses)
    smin = min(masses) / total
    return band(smin, 0.05, 0.10, 1.01, 1.01, floor=0.4)


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
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_gates.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/gates.py tests/test_gates.py
git commit -m "feat: anti-degenerate gates (repetition/density/balance/spread)"
```

---

### Task 13: Rule aggregation with determinism guarantee

**Files:**
- Create: `src/miidi/eval/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: all axes + gates.
- Produces:
  - `AXIS_WEIGHTS = {"harmony": 0.30, "voice": 0.20, "rhythm": 0.20, "structure": 0.20, "dynamics": 0.10}` (spec §6.2 聚合)
  - `RuleReport` frozen dataclass: `invalid: bool, violations: tuple, axes: dict[str, AxisResult], gates: dict[str, float], R_rule: float` with `.to_dict()` (JSON-safe)
  - `evaluate_rules(comp: Composition, defaults: StyleDefaults | None = None) -> RuleReport` — format violations ⇒ `invalid=True, R_rule=0.0`; otherwise `R_rule = 100 · Σ(wᵢ·axisᵢ) · Πgates`, clamped to [0,100]

- [ ] **Step 1: Write failing test**

`tests/test_score.py`:
```python
import json

from miidi.eval.score import evaluate_rules
from miidi.schema.model import Composition


def good_comp() -> Composition:
    melody = [(i * 480, 480, p, 88 + (i % 4) * 6)
              for i, p in enumerate([74, 76, 77, 79, 77, 76, 74, 72,
                                     74, 76, 77, 74, 72, 74, 76, 72])]
    pad = []
    pcs = [(60, 64, 67), (60, 65, 69), (59, 62, 67), (60, 64, 67)]
    for b, chord in enumerate(pcs):
        pad += [(b * 1920, 1920, p, 78) for p in chord]
        pad += [(b * 1920, 1920, p - 12, 70) for p in chord]
    bass = [(b * 960, 960, r, 92)
            for b, r in enumerate([36, 41, 43, 36, 36, 41, 43, 36])]
    drums = [(t, 120, p, 100) for rep in range(4)
             for t, p in [(rep * 1920, 36), (rep * 1920 + 960, 38),
                          (rep * 1920 + 240, 42), (rep * 1920 + 720, 42)]]
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=[{"name": "verseA", "start_bar": 0, "bars": 2},
                   {"name": "verseB", "start_bar": 2, "bars": 2}],
        harmony=[{"bar": b, "dur_bars": 1.0, "symbol": s}
                 for b, s in enumerate(["C", "F", "G", "C"])],
        tracks=[
            {"name": "Mel", "role": "melody", "program": 73, "notes": melody},
            {"name": "Pad", "role": "harmony", "program": 0, "notes": pad},
            {"name": "Bs", "role": "bass", "program": 33, "notes": bass},
            {"name": "Dr", "role": "drums", "is_drum": True, "notes": drums},
        ],
    )


def test_valid_composition_scores_in_band():
    report = evaluate_rules(good_comp())
    assert not report.invalid
    assert 40.0 <= report.R_rule <= 100.0
    assert set(report.axes) == {"harmony", "voice", "rhythm", "structure", "dynamics"}
    assert set(report.gates) == {"repetition", "density", "balance", "spread"}


def test_invalid_composition_zeroed():
    comp = good_comp()
    comp.tracks[0].notes.append((50, 480, 60, 96))
    report = evaluate_rules(comp)
    assert report.invalid and report.R_rule == 0.0
    assert report.violations


def test_bit_exact_determinism():
    a = evaluate_rules(good_comp()).to_dict()
    b = evaluate_rules(good_comp().model_copy(deep=True)).to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_degraded_scores_lower():
    good = evaluate_rules(good_comp())
    bad_comp = good_comp()
    mel = [(i * 480, 480, [72, 74, 76, 79][i % 4], 96) for i in range(16)]
    bad_comp.tracks[0].notes = mel
    bad = evaluate_rules(bad_comp)
    assert bad.R_rule < good.R_rule


def test_to_dict_json_safe():
    payload = evaluate_rules(good_comp()).to_dict()
    json.dumps(payload)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_score.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

`src/miidi/eval/score.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from miidi.eval.axes import (
    AxisResult, axis_dynamics, axis_format, axis_harmony, axis_rhythm,
    axis_structure, axis_voice,
)
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.eval.gates import gate_balance, gate_density, gate_repetition, gate_spread
from miidi.schema.model import Composition
from miidi.schema.validate import Violation

AXIS_WEIGHTS = {
    "harmony": 0.30, "voice": 0.20, "rhythm": 0.20, "structure": 0.20,
    "dynamics": 0.10,
}
GATE_NAMES = ("repetition", "density", "balance", "spread")


@dataclass(frozen=True)
class RuleReport:
    invalid: bool
    R_rule: float
    axes: dict[str, AxisResult] = field(default_factory=dict)
    gates: dict[str, float] = field(default_factory=dict)
    violations: tuple[Violation, ...] = ()

    def to_dict(self) -> dict:
        return {
            "invalid": self.invalid,
            "R_rule": round(self.R_rule, 6),
            "axes": {k: {"score": round(v.score, 6), "details": v.details}
                     for k, v in self.axes.items()},
            "gates": {k: round(v, 6) for k, v in self.gates.items()},
            "violations": [v.__dict__ for v in self.violations],
        }


def evaluate_rules(comp: Composition,
                   defaults: StyleDefaults | None = None) -> RuleReport:
    fmt_score, viols = axis_format(comp)
    if fmt_score < 1.0:
        return RuleReport(invalid=True, R_rule=0.0, violations=tuple(viols))
    ctx = EvaluationContext.from_composition(comp, defaults)
    axes = {
        "harmony": axis_harmony(ctx),
        "voice": axis_voice(ctx),
        "rhythm": axis_rhythm(ctx),
        "structure": axis_structure(ctx),
        "dynamics": axis_dynamics(ctx),
    }
    base = sum(AXIS_WEIGHTS[k] * axes[k].score for k in AXIS_WEIGHTS)
    gates = {
        "repetition": gate_repetition(ctx),
        "density": gate_density(ctx),
        "balance": gate_balance(ctx),
        "spread": gate_spread(ctx),
    }
    multiplier = 1.0
    for v in gates.values():
        multiplier *= max(v, 0.0)
    r = max(0.0, min(100.0, 100.0 * base * multiplier))
    return RuleReport(invalid=False, R_rule=r, axes=axes, gates=gates)
```

- [ ] **Step 4: Verify pass**

Run: `python -m pytest tests/test_score.py -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/miidi/eval/score.py tests/test_score.py
git commit -m "feat: rule evaluator aggregation R_rule with determinism"
```

---

### Task 14: README skeleton + suite green

**Files:**
- Create: `README.md`

**Interfaces:**
- Produces: repo entrypoint documentation sufficient to install and run tests.

- [ ] **Step 1: Write README**

`README.md`:
```markdown
# MiiDi

基于 LLM 的符号音乐（MIDI）生成与双轨评估系统。

## 状态

Kernel 核心（schema / 渲染 / 规则评估器）已实现；生成流水线、Web 应用与评测材料按计划推进（见 docs/superpowers/specs/ 与 docs/superpowers/plans/）。

## 安装

    pip install -e ".[dev]"
    cp env.example .env   # 填入 OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME

## 运行测试

    python -m pytest tests/ -v

## 设计文档

- 规格：docs/superpowers/specs/2026-08-22-miidi-design.md
- 计划：docs/superpowers/plans/
```

- [ ] **Step 2: Full suite + commit**

Run: `python -m pytest tests/ -v && git add README.md && git commit -m "docs: readme with install and test instructions"`

Expected: ALL PASS; commit created.

---

## Self-Review Notes (completed at plan time)

- Spec coverage: §4 数据模型 → Tasks 3-5; §6.2 A1→Task 9, A2→Task 9, A3/A4→Task 10, A5/A6→Task 11; §6.3 门→Task 12; 聚合公式与权重→Task 13; 渲染与 fail-soft→Task 7; GM 表/ch10/channel 分配→Tasks 6-7; 确定性→Tasks 13 (bit-exact test)。§5 流水线、§9 Web、§7/§8 样本与实验属 Plan 2-4。
- Type consistency: `AxisResult(score, details)` defined Task 9, reused 10-13; `EvaluationContext.flat_notes()/chord_at()/sections/bar_ticks/piece_end` defined Task 8, consumed everywhere; `declining`/`band` defined Tasks 9/6 respectively.
- Known simplifications documented inline: parallels detection is onset-aligned heuristic; swing consistency uses spread-of-offbeat-residues proxy; dynamics uses section-mean gradient (no autocorr). These are v1 operationalizations of spec §6.2 — revisit only if E1/E3 experiments expose failures.
