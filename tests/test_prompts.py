from pathlib import Path

import pytest

from miidi.eval.style import StyleDefaults
from miidi.pipeline.prompts import (
    compose_system, compose_user, plan_system, plan_user,
    review_system, review_user,
)


@pytest.fixture()
def pack():
    from miidi.skills.loader import load_style_pack
    return load_style_pack("pop")


def test_plan_system_contains_schema_and_contract(pack):
    text = plan_system(pack)
    assert '"instruments"' in text and '"symbol"' in text
    assert "JSON" in text and "no markdown" in text.lower()
    assert "Pop" in text or "pop" in text


def test_plan_user_embeds_range_and_vocab(pack):
    text = plan_user("一首关于夏天的歌", pack)
    assert "一首关于夏天的歌" in text
    assert "84" in text and "132" in text
    assert len(text) > 200


def test_compose_prompts_carry_grid_rules(pack):
    spec = {"name": "Lead", "program": 73, "role": "melody",
            "description": "singing quarter-note melody"}
    sys_text = compose_system(spec, pack)
    usr_text = compose_user('{"bpm": 100}', spec, "MELODY NOTES: [[0,480,72,96]]")
    assert "ppq=480" in sys_text or "480" in sys_text
    assert '"notes"' in usr_text
    assert "[[0,480,72,96]]" in usr_text


def test_review_prompt_lists_tracks():
    sys_text = review_system()
    usr = review_user("bar5 bass not chord tone", ["Bs", "Pad"], '{"bpm": 100}')
    assert '"track"' in usr and "Bs" in usr
    assert "JSON" in sys_text
