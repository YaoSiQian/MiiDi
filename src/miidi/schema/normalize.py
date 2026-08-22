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
