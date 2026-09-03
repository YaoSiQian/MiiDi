from __future__ import annotations

import math
import re
from pathlib import Path

from midiutil import MIDIFile

from miidi.musicutil.gm import assign_channels
from miidi.schema.model import PPQ, Composition


def generate_midi(comp: Composition, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", comp.meta.title).strip("_") or "untitled"
    path = out_dir / f"{safe}.mid"
    mf = MIDIFile(len(comp.tracks), deinterleave=False, ticks_per_quarternote=PPQ)
    channels = assign_channels([t.is_drum for t in comp.tracks])
    for ti, track in enumerate(comp.tracks):
        mf.addTrackName(ti, 0, track.name)
        if not track.is_drum:
            mf.addProgramChange(ti, channels[ti], 0, track.program)
        for onset, dur, pitch, vel in track.notes:
            mf.addNote(ti, channels[ti], pitch, onset / PPQ, dur / PPQ, vel)
    mf.addTempo(0, 0, comp.meta.bpm)
    num, den = comp.meta.time_signature
    if den in (2, 4, 8, 16):
        mf.addTimeSignature(0, 0, num, int(math.log2(den)), 24)
    with open(path, "wb") as fh:
        mf.writeFile(fh)
    return path
