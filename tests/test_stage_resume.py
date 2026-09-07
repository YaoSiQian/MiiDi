"""Stage-by-stage pipeline semantics: resume, per-track skip, plan-gate revise."""

from __future__ import annotations

from miidi.pipeline.orchestrator import revise, run_pipeline
from miidi.session.store import SessionStore

BRIEF = {
    "title": "T",
    "bpm": 100,
    "time_signature": [4, 4],
    "tonic_pc": 0,
    "mode": "major",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 2}],
    "harmony": [{"bar": 0, "dur_bars": 2.0, "symbol": "C"}],
    "instruments": [
        {"name": "Lead", "program": 73, "role": "melody", "description": "tune"},
        {"name": "Bs", "program": 33, "role": "bass", "description": "roots"},
    ],
}

LEAD_NOTES = {"notes": [[i * 480, 480, 60, 80] for i in range(4)]}
BASS_NOTES = {"notes": [[0, 1920, 45, 80]]}
NO_ADJUSTMENTS = {"analysis": {}, "adjustments": []}
REVIEW_NULL = {"track": None}


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


def _planned_session(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    client = FakeClient([BRIEF])
    result = run_pipeline("x", "pop", client, store=store, stages=["plan"])
    sid = result.sid
    assert sid is not None
    assert [v["label"] for v in store.list_versions(sid)] == ["planned"]
    assert len(client.calls) == 1  # brief only
    return store, client, sid


def test_resume_core_from_planned_skips_brief(tmp_path):
    store, _, sid = _planned_session(tmp_path)
    client = FakeClient([LEAD_NOTES, BASS_NOTES])
    result = run_pipeline("x", "pop", client, store=store, stages=["core"], sid=sid)

    assert result.comp is not None
    assert any("resumed" in s for s in result.stage_log)
    assert len(client.calls) == 2  # lead + bass, no brief call
    labels = [v["label"] for v in store.list_versions(sid)]
    assert labels == ["planned", "core"]
    comp = store.load_composition(sid, store.latest(sid))
    assert all(t.notes for t in comp.tracks)


def test_resume_arrange_from_core_runs_review_only(tmp_path):
    store, _, sid = _planned_session(tmp_path)
    run_pipeline("x", "pop", FakeClient([LEAD_NOTES, BASS_NOTES]), store=store,
                 stages=["core"], sid=sid)

    # BRIEF has no harmony/counter/color specs: arrange has nothing to compose,
    # but coordination + self-review still complete the pipeline.
    client = FakeClient([NO_ADJUSTMENTS, REVIEW_NULL])
    result = run_pipeline("x", "pop", client, store=store, stages=["arrange"], sid=sid)

    assert result.comp is not None
    assert len(client.calls) == 2
    labels = [v["label"] for v in store.list_versions(sid)]
    assert labels == ["planned", "core", "reviewed"]


def test_full_run_on_reviewed_session_is_noop(tmp_path):
    store, _, sid = _planned_session(tmp_path)
    run_pipeline("x", "pop", FakeClient([LEAD_NOTES, BASS_NOTES]), store=store,
                 stages=["core"], sid=sid)
    run_pipeline("x", "pop", FakeClient([NO_ADJUSTMENTS, REVIEW_NULL]), store=store,
                 stages=["arrange"], sid=sid)
    versions_before = store.list_versions(sid)

    client = FakeClient([])
    result = run_pipeline("x", "pop", client, store=store, sid=sid)

    assert result.comp is not None
    assert client.calls == []
    assert store.list_versions(sid) == versions_before


def test_revise_plan_stage_feedback_replans_only(tmp_path):
    store, _, sid = _planned_session(tmp_path)
    client = FakeClient([BRIEF])
    result = revise(store, client, sid, "make it darker")

    assert result.comp is not None
    assert len(client.calls) == 1  # re-plan, no classify / track compose
    labels = [v["label"] for v in store.list_versions(sid)]
    assert labels == ["planned", "planned"]
    # the re-planned version carries a restorable brief for the next stage
    ver = store.load_version(sid, store.latest(sid))
    assert "brief" in (ver.get("extra") or {})


def test_revise_regenerate_leaves_no_intermediate_versions(tmp_path):
    store, _, sid = _planned_session(tmp_path)
    run_pipeline("x", "pop", FakeClient([LEAD_NOTES, BASS_NOTES]), store=store,
                 stages=["core"], sid=sid)

    client = FakeClient([
        {"layer": "regenerate"},  # classify
        BRIEF,  # fresh pipeline: brief
        LEAD_NOTES,
        BASS_NOTES,
        NO_ADJUSTMENTS,
        REVIEW_NULL,
    ])
    result = revise(store, client, sid, "change everything")

    assert result.comp is not None
    labels = [v["label"] for v in store.list_versions(sid)]
    # exactly one new version — no intermediate core/assembled from the rerun
    assert labels == ["planned", "core", "revised-regenerated"]
