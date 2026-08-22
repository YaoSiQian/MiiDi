import shutil

import pytest

from miidi.render.audio import AudioUnavailableError, midi_to_wav


def test_missing_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    fake = tmp_path / "x.mid"
    fake.write_bytes(b"MThd")
    with pytest.raises(AudioUnavailableError):
        midi_to_wav(fake, soundfont=tmp_path / "s.sf2")
