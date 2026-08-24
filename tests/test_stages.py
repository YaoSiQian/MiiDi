import pytest
from pydantic import ValidationError

from miidi.eval.style import StyleDefaults
from miidi.llm.client import LLMError
from miidi.pipeline.brief import InstrumentSpec, MusicBrief
from miidi.pipeline.stages import (
    StageError, build_context, compose_track, make_brief, self_review,
)
from miidi.schema.model import Composition, Track


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def respond_json(self, system, user, temperature=0.0):
        self.calls.append((system, user))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


BRIEF_OK = {
    "title": "Summer", "bpm": 100, "time_signature": [4, 4],
    "tonic_pc": 0, "mode": "major",
    "structure": [
        {"name": "verse", "start_bar": 0, "bars": 4},
        {"name": "chorus", "start_bar": 4, "bars": 4},
    ],
    "harmony": [
        {"bar": 0, "dur_bars": 4.0, "symbol": "C"},
        {"bar": 4, "dur_bars": 4.0, "symbol": "G"},
    ],
    "instruments": [
        {"name": "Lead", "program": 73, "role": "melody", "description": "tune"},
        {"name": "Bs", "program": 33, "role": "bass", "description": "roots"},
    ],
}


def pack_pop():
    from miidi.skills.loader import load_style_pack
    return load_style_pack("pop")


def test_make_brief_happy_path():
    client = FakeClient([BRIEF_OK])
    brief = make_brief(client, pack_pop(), "summer song")
    assert brief.title == "Summer"
    comp = brief.to_skeleton()
    assert comp.tracks[0].is_drum is False
    assert comp.total_bars() == 8.0


def test_make_brief_repairs_unparseable_chord_then_fails():
    bad = {**BRIEF_OK, "harmony": [{"bar": 0, "dur_bars": 4.0, "symbol": "Cmaj9"}]}
    client = FakeClient([bad, bad])
    with pytest.raises(StageError):
        make_brief(client, pack_pop(), "x")
    assert len(client.calls) == 2


def test_make_brief_second_try_recovers():
    bad = {**BRIEF_OK, "harmony": [{"bar": 0, "dur_bars": 4.0, "symbol": "Q7"}]}
    client = FakeClient([bad, BRIEF_OK])
    assert make_brief(client, pack_pop(), "x").title == "Summer"


def test_make_brief_clamps_bpm_into_style_range():
    hot = {**BRIEF_OK, "bpm": 300}
    client = FakeClient([hot])
    brief = make_brief(client, pack_pop(), "x")
    assert pack_pop().defaults.bpm_range[0] <= brief.bpm <= pack_pop().defaults.bpm_range[1]


def test_make_brief_contiguity_repair():
    gapped = {**BRIEF_OK,
              "structure": [{"name": "a", "start_bar": 0, "bars": 2},
                            {"name": "b", "start_bar": 9, "bars": 2}]}
    client = FakeClient([gapped])
    brief = make_brief(client, pack_pop(), "x")
    assert brief.structure[1].start_bar == 2


NOTES_OK = {"notes": [[0, 480, 60, 96], [480, 480, 62, 96]]}


def test_compose_track_success():
    client = FakeClient([NOTES_OK])
    spec = {"name": "Lead", "program": 73, "role": "melody", "description": ""}
    track, repairs = compose_track(client, pack_pop(),
                                  MusicBrief.model_validate(
                                      {**BRIEF_OK}), spec, "")
    assert isinstance(track, Track)
    assert track.notes[0] == (0, 480, 60, 96)


def test_compose_track_retry_then_stage_error():
    client = FakeClient([{"notes": [[0, 480, 999, 96]]},
                         {"notes": [[0, 480, 999, 96]]},
                         {"notes": [[0, 480, 999, 96]]}])
    spec = {"name": "L", "program": 73, "role": "melody", "description": ""}
    with pytest.raises(StageError):
        compose_track(client, pack_pop(), MusicBrief.model_validate({**BRIEF_OK}),
                      spec, "")


def test_build_context_kinds():
    tracks = {"Mel": Track(name="Mel", role="melody",
                           notes=[(0, 480, 60, 96), (480, 480, 64, 96)])}
    full = build_context("full", tracks)
    assert "[[0, 480, 60, 96]" in full.replace("(", "[").replace(")", "]") or "60" in full
    summary = build_context("pc_summary", tracks)
    assert "bar" in summary.lower()


def test_self_review_stops_on_null_patch():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96), (480, 480, 64, 96),
                                            (960, 480, 67, 96), (1440, 480, 72, 96)])])
    client = FakeClient([{"track": None}])
    out, traj = self_review(client, comp, StyleDefaults(), max_rounds=2)
    assert traj[0]["round"] == 0
    assert out.tracks[0].notes == comp.tracks[0].notes


def test_self_review_applies_valid_patch():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96), (480, 480, 64, 96),
                                            (960, 480, 67, 96), (1440, 480, 72, 96)])])
    patched = {"track": "L",
               "notes": [[0, 480, 60, 80], [480, 480, 64, 90],
                         [960, 480, 67, 100], [1440, 480, 72, 110]]}
    client = FakeClient([patched, {"track": None}])
    out, traj = self_review(client, comp, StyleDefaults())
    assert out.tracks[0].notes[-1][3] == 110
    assert len(traj) >= 2


def test_self_review_rejects_invalid_patch_and_breaks():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96)])])
    client = FakeClient([{"track": "L", "notes": [[0, 480, 200, 96]]}])
    out, _traj = self_review(client, comp, StyleDefaults())
    assert out.tracks[0].notes == comp.tracks[0].notes
