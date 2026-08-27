from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from miidi.web.app import create_app
from miidi.session.store import SessionStore


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


def test_get_audio_501(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/audio")
    assert resp.status_code == 501


def test_get_versions(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert "versions" in data
    assert len(data["versions"]) > 0


def test_empty_session_returns_404(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    sid = store.create("empty", "touhou")
    app = create_app(store, FakeClient(), tmp_path)
    c = TestClient(app)
    resp = c.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 404
    resp = c.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 404


def test_evaluate(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    assert "report" in resp.json()


class ReviseFakeClient:
    def __init__(self):
        self._replies = [
            BRIEF, LEAD_NOTES, BASS_NOTES, REVIEW_NULL,
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
