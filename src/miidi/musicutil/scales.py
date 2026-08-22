from __future__ import annotations

from miidi.schema.model import KeySig

MAJOR_PCS = (0, 2, 4, 5, 7, 9, 11)
NATURAL_MINOR_PCS = (0, 2, 3, 5, 7, 8, 10)
HARMONIC_MINOR_PCS = (0, 2, 3, 5, 7, 8, 11)


def scale_pcs(key: KeySig) -> frozenset[int]:
    steps = MAJOR_PCS if key.mode == "major" else NATURAL_MINOR_PCS
    return frozenset((key.tonic_pc + s) % 12 for s in steps)


def minor_superset_pcs(key: KeySig) -> frozenset[int]:
    return frozenset((key.tonic_pc + s) % 12 for s in (*NATURAL_MINOR_PCS, 11))
