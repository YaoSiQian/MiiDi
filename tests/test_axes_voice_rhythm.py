import pytest

from miidi.eval.axes import axis_rhythm, axis_voice
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition

MELODY_PITCHES = [74, 76, 77, 79, 77, 76, 74, 72,
                  74, 76, 77, 74, 72, 74, 76, 72]


def good_tracks():
    return [
        {"name": "Mel", "role": "melody", "program": 73,
         "notes": [(i * 480, 480, p, 96) for i, p in enumerate(MELODY_PITCHES)]},
        {"name": "Bs", "role": "bass", "program": 33,
         "notes": [(i * 960, 960, p, 96)
                   for i, p in enumerate([43, 45, 47, 43, 41, 43, 45, 43])]},
    ]


def ctx_of(tracks, style="pop", defaults=None) -> EvaluationContext:
    comp = Composition(meta={"style": style},
                       structure=[{"name": "A", "start_bar": 0, "bars": 4}],
                       tracks=tracks)
    return EvaluationContext.from_composition(comp, defaults or StyleDefaults())


def test_voice_baseline_high():
    res = axis_voice(ctx_of(good_tracks()))
    assert res.details["parallel_count"] == 0
    assert res.details["range_fit"] == 1.0
    assert res.details["leap_rate"] == 0.0
    assert res.score >= 0.85


def test_out_of_range_note_penalized():
    tracks = good_tracks()
    mel = list(tracks[0]["notes"])
    mel[0] = (0, 480, 110, 96)
    tracks[0]["notes"] = mel
    res = axis_voice(ctx_of(tracks))
    assert res.details["range_fit"] < 0.95
    assert res.score < axis_voice(ctx_of(good_tracks())).score


def test_parallel_fifths_counted():
    tracks = [
        {"name": "Top", "role": "harmony", "program": 0,
         "notes": [(0, 960, 67, 96), (960, 960, 69, 96)]},
        {"name": "Bot", "role": "bass", "program": 33,
         "notes": [(0, 960, 48, 96), (960, 960, 50, 96)]},
    ]
    res = axis_voice(ctx_of(tracks))
    assert res.details["parallel_count"] >= 1


def test_leaps_penalized():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 480, 60, 96), (480, 480, 96, 96),
                  (960, 480, 60, 96), (1440, 480, 96, 96)],
    }]
    res = axis_voice(ctx_of(tracks))
    assert res.details["leap_rate"] == 1.0
    assert res.score < axis_voice(ctx_of(good_tracks())).score


def test_rhythm_grid_clean():
    res = axis_rhythm(ctx_of(good_tracks()))
    assert res.details["grid_adherence"] == 1.0
    assert res.score >= 0.8


def test_offgrid_penalized():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 480, 72, 96), (483, 480, 74, 96)],
    }]
    res = axis_rhythm(ctx_of(tracks, style="classical"))
    assert res.details["grid_adherence"] < 1.0


def test_swing_whitelist_restores_adherence():
    tracks = [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(0, 220, 72, 96), (220, 260, 74, 96),
                  (480, 220, 76, 96), (700, 260, 77, 96)],
    }]
    defaults = StyleDefaults(swing_offsets=[220, 260, 700, 740])
    res = axis_rhythm(ctx_of(tracks, style="jazz", defaults=defaults))
    assert res.details["grid_adherence"] == 1.0


def test_drum_pattern_match():
    hits = [(0, 36), (960, 38), (240, 42), (720, 42), (1200, 42), (1680, 42)]
    tracks = [{
        "name": "Dr", "role": "drums", "is_drum": True,
        "notes": [(b * 1920 + r, 120, p, 100)
                  for b in range(4) for r, p in hits],
    }]
    defaults = StyleDefaults(drum_patterns={"kick": [0], "snare": [960],
                                            "hat": [240, 720, 1200, 1680]})
    res = axis_rhythm(ctx_of(tracks, style="lofi", defaults=defaults))
    assert res.details["drum_pattern_fit"] >= 0.95


def test_density_ref_in_band_scores_high():
    defaults = StyleDefaults(density_ref={"melody": (3.0, 10.0)})
    res = axis_rhythm(ctx_of(good_tracks(), defaults=defaults))
    assert res.details["density_fit"] == pytest.approx(1.0)


def test_absurd_density_ref_penalized():
    defaults = StyleDefaults(density_ref={"melody": (40.0, 60.0)})
    res = axis_rhythm(ctx_of(good_tracks(), defaults=defaults))
    assert res.details["density_fit"] == pytest.approx(0.3)


def _offbeat_track(onsets):
    return [{
        "name": "Mel", "role": "melody", "program": 73,
        "notes": [(o, 220, p, 96)
                  for o, p in zip(onsets, [72, 74, 76, 77])],
    }]


def test_swing_consistent_offbeats_rewarded():
    tight = axis_rhythm(ctx_of(_offbeat_track([220, 700, 1180, 1660]), style="jazz"))
    assert tight.details["swing_consistency"] == pytest.approx(1.0)


def test_scattered_offbeats_penalized():
    tight = axis_rhythm(ctx_of(_offbeat_track([220, 700, 1180, 1660]), style="jazz"))
    loose = axis_rhythm(ctx_of(_offbeat_track([220, 340, 1180, 1420]), style="jazz"))
    assert loose.details["swing_consistency"] == pytest.approx(0.2)
    assert loose.score < tight.score
