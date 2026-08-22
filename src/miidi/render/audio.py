from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class AudioUnavailableError(RuntimeError):
    pass


def midi_to_wav(midi_path: Path, wav_path: Path | None = None,
                soundfont: Path | None = None) -> Path:
    binary = shutil.which("fluidsynth")
    sf = soundfont or os.environ.get("MIIDI_SOUNDFONT")
    if not binary:
        raise AudioUnavailableError("fluidsynth binary not found on PATH")
    if not sf or not Path(sf).is_file():
        raise AudioUnavailableError(f"soundfont not found: {sf!r}")
    wav_path = wav_path or midi_path.with_suffix(".wav")
    result = subprocess.run(
        [binary, "-ni", "-g", "1.0", "-F", str(wav_path), str(sf), str(midi_path)],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0 or not wav_path.exists():
        raise AudioUnavailableError(f"fluidsynth failed: {result.stderr.decode()[:400]}")
    return wav_path
