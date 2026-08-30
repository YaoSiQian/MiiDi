from __future__ import annotations

import random
from enum import Enum

from miidi.schema.model import Composition


class DegradationOp(Enum):
    SCATTER_PITCH = "scatter_pitch"
    REMOVE_TRACK = "remove_track"
    SCATTER_ONSET = "scatter_onset"
    REPEAT_FIRST_BAR = "repeat_first_bar"


def degrade_composition(
    comp: Composition, op: DegradationOp, seed: int = 42
) -> Composition:
    rng = random.Random(seed)
    new_tracks = []
    for track in comp.tracks:
        new_notes = list(track.notes)
        if op == DegradationOp.SCATTER_PITCH:
            new_notes = [
                (o, d, rng.randint(48, 84), v) for o, d, p, v in new_notes
            ]
        elif op == DegradationOp.SCATTER_ONSET:
            new_notes = [
                (o + rng.randint(-60, 60), d, p, v) for o, d, p, v in new_notes
            ]
        elif op == DegradationOp.REPEAT_FIRST_BAR:
            bar_ticks = comp.bar_ticks
            first_bar_notes = [n for n in new_notes if n[0] < bar_ticks]
            repeated = []
            total_bars = int(comp.total_bars())
            for bar in range(total_bars):
                for onset, dur, pitch, vel in first_bar_notes:
                    new_onset = onset + bar * bar_ticks
                    if new_onset + dur <= total_bars * bar_ticks:
                        repeated.append((new_onset, dur, pitch, vel))
            new_notes = repeated
        new_tracks.append(track.model_copy(update={"notes": new_notes}))

    if op == DegradationOp.REMOVE_TRACK and len(new_tracks) > 1:
        new_tracks = new_tracks[:-1]

    return comp.model_copy(update={"tracks": new_tracks})
