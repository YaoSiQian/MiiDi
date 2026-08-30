from pathlib import Path

import pytest

from miidi.llm.client import LLMError
from miidi.pipeline.orchestrator import PipelineResult, revise, run_pipeline


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


BRIEF = {
    "title": "T", "bpm": 100, "time_signature": [4, 4],
    "tonic_pc": 0, "mode": "major",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 2}],
    "harmony": [{"bar": 0, "dur_bars": 2.0, "symbol": "C"}],
    "instruments": [
        {"name": "Lead", "program": 73, "role": "melody", "description": "tune"},
        {"name": "Bs", "program": 33, "role": "bass", "description": "roots"},
    ],
}


def lead_ok(_sys, _usr):
    return {"notes": [[o * 240, 240, p, 90] for o, p in
                      enumerate([72, 74, 76, 72, 74, 76, 74, 72])]}   # spans 8 eighths=1920*... 8*240=1920 ticks = 1 bar


def bass_ok(_sys, _usr):
    return {"notes": [[0, 960, 36, 88], [960, 960, 43, 88]]}


def lead_20_bars(_sys, _usr):
    pitches = [72, 74] * 80
    return {"notes": [[o * 240, 240, p, 90] for o, p in enumerate(pitches)]}


NO_ADJUSTMENTS = {"analysis": {}, "adjustments": []}


def test_run_pipeline_end_to_end_with_fake_llm(tmp_path):
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    result = run_pipeline("a tiny tune", "pop", client, out_dir=tmp_path)
    assert isinstance(result, PipelineResult)
    assert result.comp is not None and len(result.comp.tracks) == 2
    names = {t.name for t in result.comp.tracks}
    assert names == {"Lead", "Bs"}
    assert result.midi_path is not None and Path(result.midi_path).exists()
    assert any("brief" in s for s in result.stage_log)
    assert result.trajectory and result.trajectory[0]["round"] == 0


def test_run_pipeline_saves_versions_when_store_given(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "sessions")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    result = run_pipeline("x", "pop", client, store=store)

    assert result.comp is not None
    sid = store.list_sessions()[0]
    assert store.latest(sid) >= 2


def test_run_pipeline_versions_land_in_own_session(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "sessions")
    decoy = store.create("decoy prompt", "pop")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    result = run_pipeline("x", "pop", client, store=store)
    assert result.sid is not None and result.sid != decoy
    labels = [v["label"] for v in store.list_versions(result.sid)]
    assert "assembled" in labels and "reviewed" in labels
    assert store.list_versions(decoy) == []


def test_planner_failure_returns_partial(tmp_path):
    client = FakeClient([LLMError("down")])
    result = run_pipeline("x", "pop", client)
    assert result.comp is None
    assert any("brief" in s.lower() or "fail" in s.lower() for s in result.stage_log)


def test_revise_regenerates_track(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "s")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    run_pipeline("x", "pop", client, store=store)
    sid = store.list_sessions()[0]
    quieter = {"notes": [[0, 1920, 60, 40]]}
    client2 = FakeClient([{"layer": "track", "track": "Lead"},
                          quieter, {"track": None}])
    out = revise(store, client2, sid, "make lead quieter")
    lead = next(t for t in out.comp.tracks if t.name == "Lead")
    assert lead.notes[-1][3] == 40
    assert out.sid == sid


def test_revise_regenerate_preserves_session_lineage(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "s")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    first = run_pipeline("x", "pop", client, store=store)
    sid = first.sid
    sessions_before = len(store.list_sessions())
    versions_before = len(store.list_versions(sid))
    client2 = FakeClient([{"layer": "regenerate"}, BRIEF, lead_ok(None, None),
                          bass_ok(None, None), {"track": None}])
    out = revise(store, client2, sid, "make it brighter")
    assert out.sid == sid
    assert len(store.list_versions(sid)) > versions_before
    assert len(store.list_sessions()) == sessions_before
    latest = store.load_version(sid, store.latest(sid))
    assert latest["label"] == "revised-regenerated"
    assert latest["extra"]["feedback"] == "make it brighter"


def test_validation_gate_blocks_midi_for_oversized_piece(tmp_path):
    client = FakeClient([BRIEF, lead_20_bars(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    result = run_pipeline("a long lead over a tiny form", "pop", client,
                          out_dir=tmp_path)
    assert result.comp is not None
    # Notes beyond boundary are clamped, so validation passes
    assert result.midi_path is not None


def test_self_review_llm_failure_returns_assembled_with_uniform_shape():
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, LLMError("review endpoint down")])
    result = run_pipeline("x", "pop", client)
    assert result.comp is not None and len(result.comp.tracks) == 2
    assert result.trajectory == []
    assert any(s.startswith("self-review failed") for s in result.stage_log)


def test_self_review_breaks_immediately_when_invalid_at_round_start():
    from miidi.eval.style import StyleDefaults
    from miidi.pipeline.stages import self_review
    from miidi.schema.model import Composition, Track
    comp = Composition(structure=[{"name": "verse", "start_bar": 0, "bars": 2}],
                       tracks=[Track(name="L", role="melody",
                                     notes=[(0, 19200, 60, 96)])])
    client = FakeClient([])
    _out, traj = self_review(client, comp, StyleDefaults(), max_rounds=2)
    assert client.calls == []
    assert len(traj) == 1 and traj[0]["round"] == 0
    assert "action" in traj[0]


def test_revise_regenerate_does_not_persist_gated_piece(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "s")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         NO_ADJUSTMENTS, {"track": None}])
    first = run_pipeline("x", "pop", client, store=store)
    sid = first.sid
    versions_before = len(store.list_versions(sid))
    client2 = FakeClient([{"layer": "regenerate"}, BRIEF,
                          lead_20_bars(None, None), bass_ok(None, None),
                          {"track": None}])
    out = revise(store, client2, sid, "make it much longer")
    assert out.comp is not None
    # Notes beyond boundary are clamped, so validation passes and version is persisted
    assert any("saved revised-regenerated" in s for s in out.stage_log)
    latest_label = store.load_version(sid, store.latest(sid))["label"]
    assert latest_label == "revised-regenerated"
