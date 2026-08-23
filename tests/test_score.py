import json

from miidi.eval.score import evaluate_rules
from miidi.schema.model import Composition


def good_comp() -> Composition:
    melody = [(i * 480, 480, p, 88 + (i % 4) * 6)
              for i, p in enumerate([74, 76, 77, 79, 77, 76, 74, 72,
                                     74, 76, 77, 74, 72, 74, 76, 72])]
    pad = []
    pcs = [(60, 64, 67), (60, 65, 69), (59, 62, 67), (60, 64, 67)]
    for b, chord in enumerate(pcs):
        pad += [(b * 1920, 1920, p, 78) for p in chord]
        pad += [(b * 1920, 1920, p - 12, 70) for p in chord]
    bass = [(b * 960, 960, r, 92)
            for b, r in enumerate([36, 41, 43, 36, 36, 41, 43, 36])]
    drums = [(t, 120, p, 100) for rep in range(4)
             for t, p in [(rep * 1920, 36), (rep * 1920 + 960, 38),
                          (rep * 1920 + 240, 42), (rep * 1920 + 720, 42)]]
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=[{"name": "verseA", "start_bar": 0, "bars": 2},
                   {"name": "verseB", "start_bar": 2, "bars": 2}],
        harmony=[{"bar": b, "dur_bars": 1.0, "symbol": s}
                 for b, s in enumerate(["C", "F", "G", "C"])],
        tracks=[
            {"name": "Mel", "role": "melody", "program": 73, "notes": melody},
            {"name": "Pad", "role": "harmony", "program": 0, "notes": pad},
            {"name": "Bs", "role": "bass", "program": 33, "notes": bass},
            {"name": "Dr", "role": "drums", "is_drum": True, "notes": drums},
        ],
    )


def test_valid_composition_scores_in_band():
    report = evaluate_rules(good_comp())
    assert not report.invalid
    assert 40.0 <= report.R_rule <= 100.0
    assert set(report.axes) == {"harmony", "voice", "rhythm", "structure", "dynamics"}
    assert set(report.gates) == {"repetition", "density", "balance", "spread"}


def test_invalid_composition_zeroed():
    comp = good_comp()
    comp.tracks[0].notes.append((50, 480, 60, 96))
    report = evaluate_rules(comp)
    assert report.invalid and report.R_rule == 0.0
    assert report.violations


def test_bit_exact_determinism():
    a = evaluate_rules(good_comp()).to_dict()
    b = evaluate_rules(good_comp().model_copy(deep=True)).to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_degraded_scores_lower():
    good = evaluate_rules(good_comp())
    bad_comp = good_comp()
    mel = [(i * 480, 480, [72, 74, 76, 79][i % 4], 96) for i in range(16)]
    bad_comp.tracks[0].notes = mel
    bad = evaluate_rules(bad_comp)
    assert bad.R_rule < good.R_rule


def test_to_dict_json_safe():
    payload = evaluate_rules(good_comp()).to_dict()
    json.dumps(payload)
