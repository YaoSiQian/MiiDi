from evals.experiments.e1_discrimination import DegradationOp, degrade_composition


def test_degrade_sanitize_pitch():
    from miidi.schema.model import Composition, Section, Track

    comp = Composition(
        meta={
            "title": "test",
            "bpm": 120,
            "time_signature": [4, 4],
            "key": {"tonic_pc": 0, "mode": "major"},
        },
        structure=[Section(name="verse", start_bar=0, bars=4)],
        tracks=[
            Track(
                name="Lead",
                program=73,
                role="melody",
                notes=[(0, 480, 60, 96), (480, 480, 64, 96)],
            )
        ],
    )
    degraded = degrade_composition(comp, DegradationOp.SCATTER_PITCH)
    assert degraded is not None
    assert len(degraded.tracks[0].notes) == 2
