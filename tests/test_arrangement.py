from miidi.pipeline.stages import apply_adjustments
from miidi.schema.model import Composition, Meta, Track, KeySig


def _make_comp(notes):
    return Composition(
        meta=Meta(title="Test", bpm=120, time_signature=[4, 4],
                  key=KeySig(tonic_pc=0, mode="major"), style="pop"),
        structure=[{"name": "verse", "start_bar": 0, "bars": 4}],
        harmony=[],
        tracks=[Track(name="Lead", program=73, role="melody",
                      is_drum=False, notes=notes)],
    )


def test_section_mute():
    comp = _make_comp([
        [0, 480, 60, 100],
        [1920, 480, 62, 100],
        [3840, 480, 64, 100],
        [5760, 480, 65, 100],
    ])
    result = apply_adjustments(comp, [
        {"action": "section_mute", "track": "Lead",
         "start_bar": 1, "end_bar": 3}
    ])
    pitches = [n[2] for n in result.tracks[0].notes]
    assert 60 in pitches
    assert 62 not in pitches
    assert 64 not in pitches
    assert 65 in pitches


def test_octave_shift_up():
    comp = _make_comp([[0, 480, 60, 100], [1920, 480, 72, 100]])
    result = apply_adjustments(comp, [
        {"action": "octave_shift", "track": "Lead", "direction": "up"}
    ])
    pitches = [n[2] for n in result.tracks[0].notes]
    assert pitches == [72, 84]


def test_octave_shift_down():
    comp = _make_comp([[0, 480, 72, 100], [1920, 480, 60, 100]])
    result = apply_adjustments(comp, [
        {"action": "octave_shift", "track": "Lead", "direction": "down"}
    ])
    pitches = [n[2] for n in result.tracks[0].notes]
    assert pitches == [60, 48]


def test_density_reduce():
    comp = _make_comp([
        [0, 120, 60, 100],
        [120, 120, 62, 100],
        [240, 120, 64, 100],
        [360, 120, 65, 100],
    ])
    result = apply_adjustments(comp, [
        {"action": "density_reduce", "track": "Lead",
         "start_bar": 0, "end_bar": 1, "factor": 0.5}
    ])
    assert len(result.tracks[0].notes) == 2


def test_unknown_track_ignored():
    comp = _make_comp([[0, 480, 60, 100]])
    result = apply_adjustments(comp, [
        {"action": "section_mute", "track": "Nonexistent",
         "start_bar": 0, "end_bar": 1}
    ])
    assert len(result.tracks[0].notes) == 1


def test_no_adjustments():
    comp = _make_comp([[0, 480, 60, 100], [1920, 480, 72, 100]])
    result = apply_adjustments(comp, [])
    assert len(result.tracks[0].notes) == 2
