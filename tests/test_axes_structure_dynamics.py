from miidi.eval.axes import axis_dynamics, axis_structure
from miidi.eval.context import EvaluationContext, StyleDefaults
from miidi.schema.model import Composition


def two_section_comp(sec_names, second_shift=0, velocities=None):
    vels = velocities or ([84] * 8 + [84] * 8)
    half_a = [(i * 240, 240, p, vels[i]) for i, p in
              enumerate([72, 74, 76, 74, 72, 74, 76, 79])]
    half_b = [((8 + i) * 240, 240, p + second_shift, vels[8 + i]) for i, p in
              enumerate([72, 74, 76, 74, 72, 74, 76, 79])]
    return Composition(
        meta={},
        structure=[{"name": sec_names[0], "start_bar": 0, "bars": 1},
                   {"name": sec_names[1], "start_bar": 1, "bars": 1}],
        tracks=[{"name": "M", "role": "melody", "program": 73,
                 "notes": half_a + half_b}],
    )


def ctx_of(comp) -> EvaluationContext:
    return EvaluationContext.from_composition(comp, StyleDefaults())


def test_coverage_full():
    res = axis_structure(ctx_of(two_section_comp(("verse", "verse2"))))
    assert res.details["coverage"] == 1.0


def test_repeat_family_similarity_high():
    res = axis_structure(ctx_of(two_section_comp(("verse", "verse2"))))
    assert res.details["repeat_family_sim"] >= 0.99


def test_contrast_family_low_sim_rewarded():
    same = axis_structure(ctx_of(two_section_comp(("verse", "chorus"))))
    contrast = axis_structure(
        ctx_of(two_section_comp(("verse", "chorus"), second_shift=5)))
    assert contrast.details["contrast_family_sim"] < same.details["contrast_family_sim"]
    assert contrast.score > same.score


def test_gap_in_structure_penalized():
    comp = two_section_comp(("verse", "chorus"))
    comp.structure[1].start_bar = 2          # leaves a 1-bar hole
    res = axis_structure(ctx_of(comp))
    assert res.details["coverage"] < 1.0


def test_constant_velocity_scores_low():
    comp = two_section_comp(("verse", "chorus"))
    res = axis_dynamics(ctx_of(comp))
    assert res.score <= 0.5


def test_gradient_velocity_scores_higher():
    flat = axis_dynamics(ctx_of(two_section_comp(("verse", "chorus"))))
    shaped = axis_dynamics(ctx_of(
        two_section_comp(("verse", "chorus"),
                         velocities=[82, 84, 86, 84, 82, 84, 86, 88,
                                     104, 108, 112, 108, 104, 108, 112, 116])))
    assert shaped.score > flat.score
    assert shaped.details["gradient_ok"] == 1.0
