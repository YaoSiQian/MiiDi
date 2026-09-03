from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from miidi.eval.style import StyleDefaults

_REQUIRED_FILES = ("SKILL.md", "instruments.md", "harmony.md", "rhythm.md", "defaults.json")


@dataclass(frozen=True)
class StylePack:
    name: str
    skill_md: str
    instruments_md: str
    harmony_md: str
    rhythm_md: str
    defaults: StyleDefaults


def _default_dir() -> Path:
    env = os.environ.get("MIIDI_SKILLS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "skills"


def _parse_defaults(name: str, raw: dict) -> StyleDefaults:
    try:
        density = {k: (float(v[0]), float(v[1])) for k, v in raw["density_ref"].items()}
        return StyleDefaults(
            bpm_range=(float(raw["bpm_range"][0]), float(raw["bpm_range"][1])),
            density_ref=density,
            swing_offsets=[int(x) for x in raw.get("swing_offsets", [])],
            drum_patterns={k: [int(x) for x in v] for k, v in raw.get("drum_patterns", {}).items()},
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"style {name!r}: malformed defaults.json ({exc})") from exc


def load_style_pack(name: str, skills_dir=None) -> StylePack:
    root = Path(skills_dir) if skills_dir else _default_dir()
    style_dir = root / name
    if not style_dir.is_dir():
        raise FileNotFoundError(f"unknown style {name!r} under {root}")
    texts = {}
    for f in _REQUIRED_FILES:
        p = style_dir / f
        if not p.is_file():
            raise FileNotFoundError(f"style {name!r}: missing {f}")
        texts[f] = p.read_text(encoding="utf-8")
    try:
        raw = json.loads(texts["defaults.json"])
    except json.JSONDecodeError as exc:
        raise ValueError(f"style {name!r}: defaults.json invalid JSON ({exc})") from exc
    return StylePack(
        name=name,
        skill_md=texts["SKILL.md"],
        instruments_md=texts["instruments.md"],
        harmony_md=texts["harmony.md"],
        rhythm_md=texts["rhythm.md"],
        defaults=_parse_defaults(name, raw),
    )


def available_styles(skills_dir=None) -> list[str]:
    root = Path(skills_dir) if skills_dir else _default_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "defaults.json").is_file())
