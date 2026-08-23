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


def test_non_finite_durations_reported_not_raised():
    for bad in (float("inf"), float("-inf"), float("nan"), "inf", "Infinity", "-inf"):
        res = normalize_raw({"tracks": [{"notes": [{"pitch": 60, "duration": bad}]}]})
        assert res.errors, f"no error reported for duration={bad!r}"


def test_inf_among_valid_notes_partial_success():
    res = normalize_raw({"tracks": [{"notes": [
        {"pitch": 60, "duration": float("inf")},
        {"pitch": 60, "duration": "inf"},
        {"pitch": 62, "duration": "4"},
    ]}]})
    assert any("note[0]" in e for e in res.errors)
    assert any("note[1]" in e for e in res.errors)
    assert res.composition is not None
    assert [n[2] for n in res.composition.tracks[0].notes] == [62]


def test_non_finite_onset_reported_not_raised():
    res = normalize_raw({"tracks": [{"notes": [
        {"pitch": 60, "duration": "4", "onset": float("inf")},
        {"pitch": 62, "duration": "4"},
    ]}]})
    assert any("note[0]" in e for e in res.errors)
    assert res.composition is not None
    assert [n[2] for n in res.composition.tracks[0].notes] == [62]


def test_non_finite_structure_bars_reported_not_raised():
    for bad in (float("inf"), float("-inf"), float("nan"), "inf", "Infinity", "-inf"):
        res = normalize_raw({
            "tracks": [{"notes": [[0, 240, 69, 80]]}],
            "structure": [{"name": "A", "start_bar": 0, "bars": bad}],
        })
        assert any("structure[0]" in e for e in res.errors), f"no error for bars={bad!r}"
        assert res.composition is not None
        assert res.composition.structure == []


def test_inf_structure_among_valid_partial_success():
    res = normalize_raw({
        "tracks": [{"notes": [[0, 240, 69, 80]]}],
        "structure": [{"name": "A", "bars": float("inf")},
                      {"name": "B", "start_bar": 0, "bars": 4}],
    })
    assert any("structure[0]" in e for e in res.errors)
    assert res.composition is not None
    assert [s.name for s in res.composition.structure] == ["B"]


def test_non_finite_harmony_dur_reported_not_raised():
    for bad in (float("inf"), float("-inf"), float("nan"), "inf", "Infinity"):
        res = normalize_raw({
            "tracks": [{"notes": [[0, 240, 69, 80]]}],
            "harmony": [{"bar": 0, "dur_bars": bad, "symbol": "C"}],
        })
        assert any("harmony[0]" in e for e in res.errors), f"no error for dur={bad!r}"
        assert res.composition is not None
        assert res.composition.harmony == []
