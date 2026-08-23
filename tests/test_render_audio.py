import shutil
import subprocess

import pytest

from miidi.render.audio import AudioUnavailableError, midi_to_wav


def test_missing_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    fake = tmp_path / "x.mid"
    fake.write_bytes(b"MThd")
    with pytest.raises(AudioUnavailableError):
        midi_to_wav(fake, soundfont=tmp_path / "s.sf2")


def test_fluidsynth_timeout_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/fluidsynth")
    sf = tmp_path / "s.sf2"
    sf.write_bytes(b"sf2")
    midi = tmp_path / "x.mid"
    midi.write_bytes(b"MThd")

    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fluidsynth", timeout=120)

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(AudioUnavailableError, match="timed out"):
        midi_to_wav(midi, soundfont=sf)
