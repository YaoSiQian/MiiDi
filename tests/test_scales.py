from miidi.musicutil.scales import (
    HARMONIC_MINOR_PCS, MAJOR_PCS, NATURAL_MINOR_PCS, scale_pcs,
)
from miidi.schema.model import KeySig


def test_major_scale():
    assert MAJOR_PCS == (0, 2, 4, 5, 7, 9, 11)
    assert scale_pcs(KeySig(tonic_pc=0, mode="major")) == frozenset(MAJOR_PCS)


def test_natural_minor_transposed():
    assert NATURAL_MINOR_PCS == (0, 2, 3, 5, 7, 8, 10)
    assert scale_pcs(KeySig(tonic_pc=9, mode="minor")) == frozenset(
        {(9 + x) % 12 for x in NATURAL_MINOR_PCS}
    )


def test_harmonic_minor_constant():
    assert HARMONIC_MINOR_PCS == (0, 2, 3, 5, 7, 8, 11)
