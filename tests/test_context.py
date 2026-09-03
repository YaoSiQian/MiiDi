from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def comp() -> Composition:
    return Composition(
        meta={"key": {"tonic_pc": 0, "mode": "major"}},
        structure=[
            {"name": "verse", "start_bar": 0, "bars": 2},
            {"name": "chorus", "start_bar": 2, "bars": 2},
        ],
        harmony=[
            {"bar": 0, "dur_bars": 2.0, "symbol": "C"},
            {"bar": 2, "dur_bars": 2.0, "symbol": "G"},
        ],
        tracks=[
            {
                "name": "Mel",
                "role": "melody",
                "program": 73,
                "notes": [[0, 960, 72, 96], [960, 960, 74, 96]],
            },
            {
                "name": "Bas",
                "role": "bass",
                "program": 33,
                "notes": [[0, 1920, 36, 96], [1920, 1920, 43, 96]],
            },
        ],
    )


def test_sections_resolved_to_ticks():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.sections == [("verse", 0, 3840), ("chorus", 3840, 7680)]
    assert ctx.section_of_tick(4000) == 1
    assert ctx.piece_end == 7680


def test_chord_lookup():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.chord_at(100).root_pc == 0
    assert ctx.chord_at(4000).root_pc == 7


def test_sounding_excludes_drums_optionally():
    c2 = comp()
    from miidi.schema.model import Track

    c2.tracks.append(Track(name="Dr", role="drums", is_drum=True, notes=[(0, 1920, 36, 100)]))
    ctx = EvaluationContext.from_composition(c2, StyleDefaults())
    assert len(ctx.sounding_at(0)) == 2
    assert len(ctx.sounding_at(0, exclude_drum=False)) == 3


def test_verticals_sampled_sorted():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    pairs = list(ctx.iterate_verticals())
    ticks = [t for t, _ in pairs]
    assert ticks[0] == 0 and all(b > a for a, b in zip(ticks, ticks[1:]))
    v0 = pairs[0][1]
    assert set(v0.pitch_classes) == {0}  # melody C + bass C


def test_roles_found():
    ctx = EvaluationContext.from_composition(comp(), StyleDefaults())
    assert ctx.track_of_role("melody").name == "Mel"
    assert ctx.track_of_role("drums") is None


def test_empty_structure_single_section():
    bare = Composition(tracks=[{"name": "M", "role": "melody", "notes": [[0, 480, 60, 96]]}])
    ctx = EvaluationContext.from_composition(bare, StyleDefaults())
    assert ctx.sections == [("all", 0, 1920)]  # nominal single bar minimum
