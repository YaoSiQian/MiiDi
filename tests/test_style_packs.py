import json

import pytest

from miidi.schema.chords import parse_chord
from miidi.skills.loader import available_styles, load_style_pack

EXPECTED = ["classical", "jazz", "lofi", "pop", "touhou"]


def test_all_styles_present():
    assert available_styles() == EXPECTED


@pytest.mark.parametrize("name", EXPECTED)
def test_pack_loads_and_structure(name):
    pack = load_style_pack(name)
    for attr in ("skill_md", "instruments_md", "harmony_md", "rhythm_md"):
        assert getattr(pack, attr).strip(), f"{name}.{attr} empty"
    skill = pack.skill_md
    assert "## Identity" in skill and "## Workflow" in skill and "## Output Rules" in skill
    assert "| role |" in pack.instruments_md and "GM program" in pack.instruments_md
    assert "# Harmony Vocabulary" in pack.harmony_md
    assert "## Cadences" in pack.harmony_md
    assert "## Drum Patterns" in pack.rhythm_md or name == "classical"
    assert "ppq=480" in skill or "480" in skill


@pytest.mark.parametrize("name", EXPECTED)
def test_every_chord_symbol_parses(name):
    import re
    pack = load_style_pack(name)
    body = pack.harmony_md.replace("##", " ").replace("#", " ")
    tokens = re.findall(r"\b([A-G][b#]?(?:maj7|m7b5|m7|min|m|dim7|dim|aug|sus4|sus2|add9|6|m6|7|5)?)\b",
                        body)
    checked = 0
    for t in tokens:
        if len(t) == 1 and t in "ABDEFG":
            continue
        parse_chord(t)
        checked += 1
    assert checked >= 6, f"{name}: too few chord symbols enumerated"


def test_defaults_match_contract():
    contract = {
        "pop": {"bpm": (84, 132), "swing": []},
        "classical": {"bpm": (60, 168), "swing": []},
        "jazz": {"bpm": (110, 208), "swing": [200]},
        "lofi": {"bpm": (66, 92), "swing": [180]},
        "touhou": {"bpm": (120, 170), "swing": []},
    }
    for name, want in contract.items():
        d = load_style_pack(name).defaults
        assert tuple(d.bpm_range) == want["bpm"], name
        assert list(d.swing_offsets) == want["swing"], name
        assert "__global__" in d.density_ref, name
    assert load_style_pack("classical").defaults.drum_patterns == {}
    for n in ("pop", "jazz", "lofi", "touhou"):
        dp = load_style_pack(n).defaults.drum_patterns
        assert set(dp) >= {"kick", "snare", "hat"}, n
    assert load_style_pack("jazz").defaults.swing_offsets == [200]


@pytest.mark.parametrize("name,kw", [
    ("pop", ["I-V-vi-IV"]),
    ("classical", ["cadence"]),
    ("jazz", ["ii-V-I"]),
    ("lofi", ["maj7"]),
    ("touhou", ["trumpet"]),
])
def test_identity_keywords(name, kw):
    text = load_style_pack(name)
    blob = (text.skill_md + text.harmony_md + text.instruments_md).lower()
    for k in kw:
        assert k.lower() in blob, f"{name} missing keyword {k}"
