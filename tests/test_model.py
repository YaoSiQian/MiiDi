import pytest
from pydantic import ValidationError

from miidi.schema.model import Composition, KeySig, Meta, PPQ, Section, Track


def base_meta(**kw):
    return Meta(key=KeySig(tonic_pc=0), **kw)


def test_ppq_constant():
    assert PPQ == 480


def test_valid_composition():
    comp = Composition(
        meta=base_meta(),
        structure=[Section(name="A", start_bar=0, bars=4)],
        harmony=[{"bar": 0, "dur_bars": 1.0, "symbol": "C"}],
        tracks=[
            {"name": "Lead", "program": 73, "role": "melody",
             "notes": [[0, 240, 69, 96]]},
            {"name": "Drums", "role": "drums", "is_drum": True,
             "notes": [[0, 120, 36, 100]]},
        ],
    )
    assert comp.tracks[0].notes == [(0, 240, 69, 96)]
    assert comp.bar_ticks == 1920
    assert comp.total_bars() == 4.0
    assert comp.piece_end_tick() >= 1920


def test_note_tuple_constraints():
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(0, 240, 69)])
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(0, 240, 69, 200)])
    with pytest.raises(ValidationError):
        Track(name="x", notes=[(-1, 240, 69, 96)])


def test_program_and_role_constrained():
    with pytest.raises(ValidationError):
        Track(name="x", program=128)
    with pytest.raises(ValidationError):
        Track(name="x", role="vocalist")


def test_bpm_bounds():
    with pytest.raises(ValidationError):
        base_meta(bpm=10)
    assert base_meta(bpm=300).bpm == 300


def test_time_signature_constrained():
    assert base_meta(time_signature=(6, 8)).time_signature == (6, 8)
    for bad in ([4, 0], [0, 4], [4, 3], [4, 32], [-2, 4]):
        with pytest.raises(ValidationError):
            base_meta(time_signature=bad)
