from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.eval.gates import gate_balance, gate_density, gate_repetition, gate_spread
from miidi.schema.model import Composition


def ctx_of(tracks, defaults=None) -> EvaluationContext:
    comp = Composition(meta={},
                       structure=[{"name": "A", "start_bar": 0, "bars": 4}],
                       tracks=tracks)
    return EvaluationContext.from_composition(comp, defaults or StyleDefaults())


VARIED = [(i * 480, 480, p, 96) for i, p in
          enumerate([74, 76, 77, 79, 77, 76, 74, 72,
                     74, 76, 77, 74, 72, 74, 76, 72])]


def test_repetition_clean_track():
    assert gate_repetition(ctx_of([{"name": "M", "role": "melody",
                                    "program": 73, "notes": VARIED}])) >= 0.95


def test_repetition_copy_paste_penalized():
    looped = [(i * 480, 480, p, 96) for i, p in enumerate([74, 76, 77, 79] * 8)]
    assert gate_repetition(ctx_of([{"name": "M", "role": "melody",
                                    "program": 73, "notes": looped}])) <= 0.5


def test_density_extremes():
    normal = ctx_of([{"name": "M", "role": "melody", "program": 73, "notes": VARIED}])
    stuffed = [{"name": "M", "role": "melody", "program": 73,
                "notes": [(i * 60, 60, 60 + (i % 5), 96) for i in range(512)]}]
    assert gate_density(normal) == 1.0
    assert gate_density(ctx_of(stuffed)) <= 0.6


def test_balance_stub_track_penalized():
    tracks = [
        {"name": "A", "role": "harmony", "program": 0,
         "notes": [(b * 1920, 1920, p, 80) for b, p in
                   enumerate([60, 62, 64, 65])]},
        {"name": "B", "role": "harmony", "program": 0,
         "notes": [(b * 1920, 1920, p, 80) for b, p in
                   enumerate([67, 69, 71, 72])]},
        {"name": "Stub", "role": "color", "program": 73,
         "notes": [(0, 120, 90, 80)]},
    ]
    balanced = tracks[:2]
    assert gate_balance(ctx_of(balanced)) == 1.0
    assert gate_balance(ctx_of(tracks)) <= 0.7


def test_spread_real_vs_fake():
    real = ctx_of([{"name": "M", "role": "melody", "program": 0,
                    "notes": [(i * 240, 240, 48 + ((i * 7) % 37), 96)
                              for i in range(32)]}])
    fake_notes = list(VARIED) + [(7680, 480, 127, 96), (8160, 480, 126, 96),
                                 (8640, 480, 125, 96)]
    fake = ctx_of([{"name": "M", "role": "melody", "program": 0,
                    "notes": fake_notes}])
    assert gate_spread(real) > gate_spread(fake)
