from miidi.eval.axes import axis_format, axis_harmony
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def build(harmony_symbols=("C", "F", "G", "C"), melody=(72, 74, 76, 72),
          extra_pad_notes=(), structure=None):
    pad = []
    for bar, pcs in enumerate([(60, 64, 67), (60, 65, 69), (59, 62, 67), (60, 64, 67)]):
        onset = bar * 1920
        pad += [(onset, 1920, p, 80) for p in pcs]
    pad += tuple(extra_pad_notes)
    bass = [(bar * 1920, 1920, root, 96)
            for bar, root in enumerate([36, 41, 43, 36])]
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=structure or [{"name": "A", "start_bar": 0, "bars": 4}],
        harmony=[{"bar": b, "dur_bars": 1.0, "symbol": s}
                 for b, s in enumerate(harmony_symbols)],
        tracks=[
            {"name": "Mel", "role": "melody", "program": 73,
             "notes": [(b * 1920, 1920, p, 96) for b, p in enumerate(melody)]},
            {"name": "Pad", "role": "harmony", "program": 0, "notes": pad},
            {"name": "Bs", "role": "bass", "program": 33, "notes": bass},
        ],
    )


def ctx_of(comp) -> EvaluationContext:
    return EvaluationContext.from_composition(comp, StyleDefaults())


def test_axis_format_gate():
    good = build()
    assert axis_format(good) == (1.0, [])
    bad = good.model_copy(deep=True)
    bad.tracks[0].notes.append((100, 480, 60, 96))
    score, viols = axis_format(bad)
    assert score == 0.0 and viols


def test_good_progression_high_score():
    res = axis_harmony(ctx_of(build()))
    assert res.details["scale_adherence"] == 1.0
    assert res.details["chord_support"] == 1.0
    assert res.details["declaration_match"] == 1.0
    assert res.details["cluster_rate"] == 0.0
    assert res.details["cadence_rate"] == 1.0
    assert res.score >= 0.85


def test_offkey_note_lowers_adherence_and_score():
    good_comp, good = build(), None
    good = axis_harmony(ctx_of(good_comp))
    bad_comp = good_comp.model_copy(deep=True)
    mel = list(bad_comp.tracks[0].notes)
    mel[2] = (3840, 1920, 66, 96)          # F#4 against C major
    bad_comp.tracks[0].notes = mel
    bad = axis_harmony(ctx_of(bad_comp))
    assert bad.details["scale_adherence"] < good.details["scale_adherence"]
    assert bad.score < good.score


def test_cluster_penalizes():
    good = axis_harmony(ctx_of(build()))
    clashing = build(extra_pad_notes=((0, 1920, 61, 80),))   # C + C#
    bad = axis_harmony(ctx_of(clashing))
    assert bad.details["cluster_rate"] > 0.0
    assert bad.score < good.score


def test_declaration_mismatch_detected():
    plain = axis_harmony(ctx_of(build()))
    mismatched = build(harmony_symbols=("Cmaj7", "F", "G", "C"))
    bad = axis_harmony(ctx_of(mismatched))
    assert bad.details["declaration_match"] < plain.details["declaration_match"]
