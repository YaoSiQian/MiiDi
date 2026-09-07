from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from miidi.session.store import SessionStore
from miidi.web.app import create_app

BRIEF = {
    "title": "Test Piece",
    "bpm": 140,
    "time_signature": [4, 4],
    "tonic_pc": 9,
    "mode": "minor",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 4}],
    "harmony": [{"bar": 0, "dur_bars": 4.0, "symbol": "Am"}],
    "instruments": [
        {"name": "Lead", "program": 80, "role": "melody", "description": "tune"},
        {"name": "Bass", "program": 33, "role": "bass", "description": "roots"},
    ],
}

LEAD_NOTES = {"notes": [[i * 480, 480, 60, 80] for i in range(4)]}
BASS_NOTES = {"notes": [[0, 1920, 45, 80]]}
REVIEW_NULL = {"track": None}


class FakeClient:
    def __init__(self):
        self._replies = [BRIEF, LEAD_NOTES, BASS_NOTES, REVIEW_NULL]
        self._idx = 0

    def respond_json(self, system, user, temperature=0.0):
        reply = self._replies[self._idx]
        self._idx += 1
        return reply


@pytest.fixture
def client(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, FakeClient(), tmp_path)
    return TestClient(app)


def test_create_session(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    assert resp.status_code == 200
    data = resp.json()
    assert "sid" in data


def test_get_status(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 200
    assert resp.json()["sid"] == sid


def test_get_composition(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 200


def test_404_for_unknown_session(client):
    resp = client.get("/api/sessions/nonexistent/status")
    assert resp.status_code == 404


def test_get_midi_on_demand(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = c.get(f"/api/sessions/{sid}/midi")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/midi"


def test_get_versions(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert "versions" in data
    assert len(data["versions"]) > 0


def test_empty_session_returns_planned(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    sid = store.create("empty", "touhou")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 200
    assert resp.json()["stage"] == "planned"
    resp = c.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 404


class _MockJudgeClient:
    """Minimal mock for LLMClient used by evaluate_judge."""

    def __init__(self):
        self._replies = [
            {"score": 80, "per_item": [], "evidence": []},
            {"score": 75, "per_item": [], "evidence": []},
            {"score": 70, "per_item": [], "evidence": []},
        ]
        self._idx = 0

    def respond_json(self, system, user, temperature=0.0):
        reply = self._replies[self._idx]
        self._idx += 1
        return reply

    def close(self):
        pass


def test_evaluate(tmp_path):
    from unittest.mock import patch

    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    mock_client = _MockJudgeClient()
    with (
        patch("miidi.llm.client.LLMClient", return_value=mock_client),
        patch("miidi.llm.client.load_config", return_value=None),
    ):
        resp = c.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert "composite" in data


def test_evaluate_composite(tmp_path):
    from unittest.mock import patch

    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    mock_client = _MockJudgeClient()
    with (
        patch("miidi.llm.client.LLMClient", return_value=mock_client),
        patch("miidi.llm.client.load_config", return_value=None),
    ):
        resp = c.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert "composite" in data
    assert data["composite"] is not None
    assert "composite" in data["composite"]
    assert "R_rule" in data["composite"]


class ReviseFakeClient:
    def __init__(self):
        self._replies = [
            BRIEF,
            LEAD_NOTES,
            BASS_NOTES,
            REVIEW_NULL,
            {"layer": "track", "track": "Lead"},
            {"notes": [[i * 480, 480, 62, 80] for i in range(4)]},
        ]
        self._idx = 0

    def respond_json(self, system, user, temperature=0.0):
        reply = self._replies[self._idx]
        self._idx += 1
        return reply


def test_revise(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, ReviseFakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = c.post(f"/api/sessions/{sid}/revise", json={"feedback": "make lead higher"})
    assert resp.status_code == 200
    assert resp.json()["sid"] == sid
    assert resp.json()["stage"] == "done"


def test_rollback(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    versions_before = len(store.list_versions(sid))
    resp = c.post(f"/api/sessions/{sid}/versions/1/rollback")
    assert resp.status_code == 200
    assert resp.json()["stage"] == "rolled_back"
    assert len(store.list_versions(sid)) == versions_before + 1
    latest = store.latest(sid)
    v = store.load_version(sid, latest)
    assert v["label"] == "rollback to v1"


class LifecycleFakeClient:
    def __init__(self):
        self._replies = [
            # 1. create_session plan: make_brief
            BRIEF,
            # 2. generate (resume from planned — no re-plan): core melody + bass
            LEAD_NOTES,
            BASS_NOTES,
            # 3. generate arrange_coordinate (no arrange-role specs, still runs)
            {"analysis": {}, "adjustments": []},
            # 4. generate self_review
            REVIEW_NULL,
            # 5. revise classify → single-track
            {"layer": "track", "track": "Lead"},
            # 6. revise compose Lead
            {"notes": [[i * 480, 480, 64, 80] for i in range(4)]},
        ]
        self._idx = 0

    def respond_json(self, system, user, temperature=0.0):
        reply = self._replies[self._idx]
        self._idx += 1
        return reply


def test_full_lifecycle(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    app = create_app(store, LifecycleFakeClient(), tmp_path)
    c = TestClient(app)

    resp = c.post("/api/sessions", json={"prompt": "dark and moody", "style": "jazz"})
    assert resp.status_code == 200
    sid = resp.json()["sid"]

    resp = c.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 200

    resp = c.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 200

    from unittest.mock import patch

    mock_client = _MockJudgeClient()
    with (
        patch("miidi.llm.client.LLMClient", return_value=mock_client),
        patch("miidi.llm.client.load_config", return_value=None),
    ):
        resp = c.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    assert "report" in resp.json()

    resp = c.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200
    versions_before = resp.json()["versions"]

    resp = c.post(f"/api/sessions/{sid}/generate", json={"stages": ["plan", "core", "arrange"]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True

    # generate runs in a background thread — poll until it settles
    import time

    for _ in range(200):
        resp = c.get(f"/api/sessions/{sid}/status")
        if resp.json()["stage"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert resp.json()["stage"] == "done"

    resp = c.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200
    versions_after_gen = resp.json()["versions"]
    assert len(versions_after_gen) > len(versions_before)

    resp = c.post(f"/api/sessions/{sid}/revise", json={"feedback": "make it brighter"})
    assert resp.status_code == 200

    resp = c.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200
    assert len(resp.json()["versions"]) > len(versions_after_gen)

    resp = c.get(f"/api/sessions/{sid}/midi")
    assert resp.status_code in (200, 404)


class _NoLLMClient:
    def respond_json(self, *args, **kwargs):
        raise RuntimeError("no llm in test")


def test_list_sessions_endpoint(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    store.create("first prompt", "pop")
    store.create("second prompt", "jazz")
    app = create_app(store, _NoLLMClient(), tmp_path)
    c = TestClient(app)

    resp = c.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 2
    assert {s["prompt"] for s in sessions} == {"first prompt", "second prompt"}
    assert {s["style"] for s in sessions} == {"pop", "jazz"}
    assert all(isinstance(s["versions"], list) for s in sessions)


def test_generate_stage_rejects_invalid_stages(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    sid = store.create("p", "pop")
    app = create_app(store, _NoLLMClient(), tmp_path)
    c = TestClient(app)

    resp = c.post(f"/api/sessions/{sid}/generate", json={"stages": ["bogus"]})
    assert resp.status_code == 400

    resp = c.post(f"/api/sessions/{sid}/generate", json={"stages": ["core"]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    # background thread fails fast (no LLM) — status must settle on error
    import time

    for _ in range(200):
        st = c.get(f"/api/sessions/{sid}/status").json()["stage"]
        if st in ("done", "error"):
            break
        time.sleep(0.05)
    assert st == "error"
