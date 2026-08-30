from evals.samples.schema import EvalSample


def test_eval_sample_minimal():
    sample = EvalSample(
        id="pop_basic_01",
        style="pop",
        prompt="Write a happy pop song about summer",
    )
    assert sample.id == "pop_basic_01"
    assert sample.style == "pop"
    assert sample.constraints == {}
    assert sample.expectations == {}


def test_eval_sample_full():
    sample = EvalSample(
        id="constraint_01",
        style="jazz",
        prompt="A smooth jazz piece in D minor",
        constraints={"bpm": 120, "key": "D minor", "duration_bars": 32},
        expectations={"style_features": ["swing eighth notes", "walking bass"]},
    )
    assert sample.constraints["bpm"] == 120
    assert len(sample.expectations["style_features"]) == 2


def test_sample_type_property():
    # Test basic type
    sample = EvalSample(id="pop_basic_01", style="pop", prompt="test")
    assert sample.sample_type == "basic"

    # Test constraint type
    sample = EvalSample(id="constraint_01", style="jazz", prompt="test")
    assert sample.sample_type == "constraint"

    # Test hard type
    sample = EvalSample(id="hard_01", style="classical", prompt="test")
    assert sample.sample_type == "hard"

    # Test adversarial type
    sample = EvalSample(id="adversarial_01", style="pop", prompt="test")
    assert sample.sample_type == "adversarial"
