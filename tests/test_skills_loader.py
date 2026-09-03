import json

import pytest

from miidi.eval.style import StyleDefaults
from miidi.skills.loader import available_styles, load_style_pack


@pytest.fixture()
def pack_dir(tmp_path):
    root = tmp_path / "skills"
    style = root / "teststyle"
    style.mkdir(parents=True)
    for f in ("SKILL.md", "instruments.md", "harmony.md", "rhythm.md"):
        (style / f).write_text(f"# {f}\n")
    (style / "defaults.json").write_text(
        json.dumps(
            {
                "bpm_range": [70, 140],
                "density_ref": {"__global__": [4, 24], "melody": [2, 10]},
                "swing_offsets": [200],
                "drum_patterns": {"kick": [0]},
            }
        )
    )
    return root


def test_load_pack_maps_defaults(pack_dir):
    pack = load_style_pack("teststyle", skills_dir=pack_dir)
    assert pack.name == "teststyle"
    assert isinstance(pack.defaults, StyleDefaults)
    assert pack.defaults.bpm_range == (70.0, 140.0)
    assert pack.defaults.density_ref["melody"] == (2, 10)
    assert pack.defaults.swing_offsets == [200]
    assert pack.skill_md.startswith("# SKILL.md")


def test_missing_file_raises(pack_dir):
    (pack_dir / "teststyle" / "rhythm.md").unlink()
    with pytest.raises(FileNotFoundError):
        load_style_pack("teststyle", skills_dir=pack_dir)


def test_unknown_style_raises(pack_dir):
    with pytest.raises(FileNotFoundError):
        load_style_pack("nope", skills_dir=pack_dir)


def test_available_styles_sorted(pack_dir):
    assert available_styles(skills_dir=pack_dir) == ["teststyle"]


def test_malformed_defaults_raise(pack_dir):
    (pack_dir / "teststyle" / "defaults.json").write_text('{"bpm_range": [1]}')
    with pytest.raises(ValueError):
        load_style_pack("teststyle", skills_dir=pack_dir)


def test_env_var_resolution(pack_dir, monkeypatch):
    monkeypatch.setenv("MIIDI_SKILLS_DIR", str(pack_dir))
    assert load_style_pack("teststyle").name == "teststyle"
