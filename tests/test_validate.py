from miidi.schema.model import Composition, Track
from miidi.schema.validate import validate_composition


def comp_with(track: Track) -> Composition:
    return Composition(tracks=[track])


def test_clean_passes_with_chord():
    c = comp_with(Track(name="L", notes=[(0, 240, 60, 96), (0, 240, 64, 96),
                                         (240, 240, 67, 96)]))
    assert validate_composition(c) == []


def test_partial_overlap_detected():
    c = comp_with(Track(name="L", notes=[(0, 480, 60, 96), (240, 480, 64, 96)]))
    vs = validate_composition(c)
    assert any(v.code == "OVERLAP" and "L" in v.location for v in vs)


def test_pitch_velocity_ranges():
    c = comp_with(Track(name="L", notes=[(0, 240, 128, 96), (240, 240, 60, 0)]))
    codes = {v.code for v in validate_composition(c)}
    assert codes == {"PITCH_RANGE", "VELOCITY_RANGE"}


def test_bounds_vs_structure():
    ok = Composition(
        structure=[{"name": "A", "start_bar": 0, "bars": 2}],
        tracks=[Track(name="L", notes=[(1920, 1920, 60, 96)])],
    )
    assert validate_composition(ok) == []
    bad = Composition(
        structure=[{"name": "A", "start_bar": 0, "bars": 1}],
        tracks=[Track(name="L", notes=[(1800, 480, 60, 96)])],
    )
    assert any(v.code == "BOUNDS" for v in validate_composition(bad))


def test_no_structure_uses_played_extent():
    assert validate_composition(comp_with(Track(name="L", notes=[(0, 960, 60, 96)]))) == []


def test_drum_role_consistency():
    c = comp_with(Track(name="D", role="melody", is_drum=True,
                        notes=[(0, 120, 38, 100)]))
    assert any(v.code == "DRUM_ROLE" for v in validate_composition(c))


def test_violation_location_specific():
    c = comp_with(Track(name="Bass", notes=[(0, 240, 200, 96)]))
    vs = validate_composition(c)
    assert vs[0].location == "Bass/note0"
