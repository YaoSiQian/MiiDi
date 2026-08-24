import pytest

from miidi.schema.model import Composition, Track
from miidi.session.store import SessionStore


def comp():
    return Composition(tracks=[Track(name="L", notes=[(0, 480, 60, 96)])])


def test_create_and_versions(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create("rainy lofi", "lofi")
    v1 = store.save_version(sid, "initial", comp(), {"R_rule": 55.0})
    v2 = store.save_version(sid, "reviewed", comp(), None)
    assert (v1, v2) == (1, 2)
    versions = store.list_versions(sid)
    assert [v["label"] for v in versions] == ["initial", "reviewed"]
    loaded = store.load_version(sid, 1)
    assert loaded["composition"]["tracks"][0]["name"] == "L"
    assert store.latest(sid) == 2


def test_unknown_session_raises(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.list_versions("nope")
