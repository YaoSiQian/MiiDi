from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.eval.gates import gate_balance, gate_density, gate_repetition, gate_spread
from miidi.schema.model import Composition


def ctx_of(tracks, defaults=None) -> EvaluationContext:
    comp = Composition(meta={}, structure=[{"name": "A", "start_bar": 0, "bars": 4}], tracks=tracks)
    return EvaluationContext.from_composition(comp, defaults or StyleDefaults())


VARIED = [
    (i * 480, 480, p, 96)
    for i, p in enumerate([74, 76, 77, 79, 77, 76, 74, 72, 74, 76, 77, 74, 72, 74, 76, 72])
]


def test_repetition_clean_track():
    assert (
        gate_repetition(ctx_of([{"name": "M", "role": "melody", "program": 73, "notes": VARIED}]))
        >= 0.95
    )


def test_repetition_copy_paste_penalized():
    looped = [(i * 480, 480, p, 96) for i, p in enumerate([74, 76, 77, 79] * 8)]
    assert (
        gate_repetition(ctx_of([{"name": "M", "role": "melody", "program": 73, "notes": looped}]))
        <= 0.5
    )


def test_density_extremes():
    normal = ctx_of([{"name": "M", "role": "melody", "program": 73, "notes": VARIED}])
    stuffed = [
        {
            "name": "M",
            "role": "melody",
            "program": 73,
            "notes": [(i * 60, 60, 60 + (i % 5), 96) for i in range(512)],
        }
    ]
    assert gate_density(normal) == 1.0
    assert gate_density(ctx_of(stuffed)) <= 0.6


def _melody(role="melody", name="Lead", program=73):
    return {"name": name, "role": role, "program": program, "notes": list(VARIED)}


def _bass():
    return {
        "name": "Bass",
        "role": "bass",
        "program": 33,
        "notes": [(b * 1920, 1920, p, 80) for b, p in enumerate([48, 50, 43, 45])],
    }


def test_balance_stub_track_penalized():
    balanced = [_melody(), _bass()]
    assert gate_balance(ctx_of(balanced)) == 1.0
    stub = {"name": "Stub", "role": "color", "program": 73, "notes": [(0, 120, 90, 80)]}
    assert gate_balance(ctx_of(balanced + [stub])) <= 0.7


def test_balance_missing_core_track_penalized():
    # 只有和声轨：缺 melody / bass 核心轨，乘法门必须惩罚（删轨反升盲区的修复）
    harmony_only = [
        {
            "name": "Pad",
            "role": "harmony",
            "program": 0,
            "notes": [(b * 1920, 1920, p, 80) for b, p in enumerate([60, 62, 64, 65])],
        }
    ]
    assert gate_balance(ctx_of(harmony_only)) < 1.0
    # 缺两条核心轨的惩罚应重于缺一条
    assert gate_balance(ctx_of([_melody(), harmony_only[0]])) > gate_balance(
        ctx_of(harmony_only)
    )


def test_balance_drums_required_only_when_style_expects_them():
    from miidi.eval.style import StyleDefaults

    melody_bass = [_melody(), _bass()]
    pop_defaults = StyleDefaults(drum_patterns={"kick": [0]})
    classical_defaults = StyleDefaults()
    # classical 无鼓期望 / pop 但整曲不含鼓轨（prompt 驱动的织体）→ 不惩罚
    assert gate_balance(ctx_of(melody_bass, classical_defaults)) == 1.0
    assert gate_balance(ctx_of(melody_bass, pop_defaults)) == 1.0
    # pop 且带鼓轨但被掏空（<4 音）→ 惩罚
    gutted_drums = {"name": "Drums", "role": "drums", "is_drum": True, "notes": [(0, 120, 36, 90)]}
    assert gate_balance(ctx_of(melody_bass + [gutted_drums], pop_defaults)) < 1.0


def test_spread_real_vs_fake():
    real = ctx_of(
        [
            {
                "name": "M",
                "role": "melody",
                "program": 0,
                "notes": [(i * 240, 240, 48 + ((i * 7) % 37), 96) for i in range(32)],
            }
        ]
    )
    fake_notes = list(VARIED) + [(7680, 480, 127, 96), (8160, 480, 126, 96), (8640, 480, 125, 96)]
    fake = ctx_of([{"name": "M", "role": "melody", "program": 0, "notes": fake_notes}])
    assert gate_spread(real) > gate_spread(fake)
