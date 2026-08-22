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
