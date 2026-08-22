from miidi.schema.normalize import normalize_raw


def clean(data):
    res = normalize_raw(data)
    assert res.errors == [], res.errors
    return res.composition


def test_canonical_arrays_passthrough():
    comp = clean({"tracks": [{"name": "L", "notes": [[0, 240, 69, 80]]}]})
    assert comp.tracks[0].notes == [(0, 240, 69, 80)]


def test_object_note_string_pitch_value_duration():
    comp = clean({"tracks": [{"name": "L", "notes": [
        {"pitch": "C4", "duration": "4"},
        {"pitch": "E4", "duration": "8"},
    ]}]})
    assert comp.tracks[0].notes[0] == (0, 480, 60, 96)
    assert comp.tracks[0].notes[1] == (480, 240, 64, 96)


def test_numeric_duration_is_beats():
    comp = clean({"tracks": [{"notes": [{"pitch": 60, "duration": 0.5, "velocity": 40}]}]})
    assert comp.tracks[0].notes == [(0, 240, 60, 40)]


def test_explicit_onset_respected_and_cursor_follows():
    comp = clean({"tracks": [{"notes": [
        {"pitch": 60, "duration": "4"},
        {"pitch": 62, "duration": "4", "onset": 960},
        {"pitch": 64, "duration": "4"},
    ]}]})
    onsets = [n[0] for n in comp.tracks[0].notes]
    assert onsets == [0, 960, 1440]


def test_string_pitch_variants():
    comp = clean({"tracks": [{"notes": [
        {"pitch": "F#5", "duration": "4"},
        {"pitch": "Bb3", "duration": "4"},
    ]}]})
    assert [n[2] for n in comp.tracks[0].notes] == [78, 58]


def test_drums_inferred_from_role():
    comp = clean({"tracks": [{"name": "D", "role": "drums",
                              "notes": [[0, 120, 36, 100]]}]})
    assert comp.tracks[0].is_drum is True


def test_bad_pitch_reported_not_fatal():
    res = normalize_raw({"tracks": [{"notes": [
        {"pitch": "Q4", "duration": "4"},
        {"pitch": "C4", "duration": "4"},
    ]}]})
    assert res.composition is not None
    assert len(res.composition.tracks[0].notes) == 1
    assert any("note[0]" in e for e in res.errors)


def test_unrepairable_returns_none():
    res = normalize_raw("not a dict")
    assert res.composition is None and res.errors


def test_empty_tracks_returns_none():
    res = normalize_raw({"tracks": []})
    assert res.composition is None


def test_unknown_duration_is_error_not_default():
    res = normalize_raw({"tracks": [{"notes": [{"pitch": 60, "duration": "?"}]}]})
    assert res.errors
