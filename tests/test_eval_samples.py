from pathlib import Path

import yaml

from evals.schema import EvalSample


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


def test_load_all_basic_samples():
    samples_dir = Path(__file__).parent.parent / "evals" / "samples"
    loaded = []
    for f in sorted(samples_dir.glob("*_basic_*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        sample = EvalSample(**data)
        loaded.append(sample)
    assert len(loaded) == 20
    styles = {s.style for s in loaded}
    assert styles == {"pop", "classical", "jazz", "lofi", "touhou"}


def test_load_all_constraint_samples():
    samples_dir = Path(__file__).parent.parent / "evals" / "samples"
    loaded = []
    for f in sorted(samples_dir.glob("constraint_*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        sample = EvalSample(**data)
        loaded.append(sample)
    assert len(loaded) == 8


def test_load_all_hard_samples():
    samples_dir = Path(__file__).parent.parent / "evals" / "samples"
    loaded = []
    for f in sorted(samples_dir.glob("hard_*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        sample = EvalSample(**data)
        loaded.append(sample)
    assert len(loaded) == 6


def test_load_all_adversarial_samples():
    samples_dir = Path(__file__).parent.parent / "evals" / "samples"
    loaded = []
    for f in sorted(samples_dir.glob("adversarial_*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        sample = EvalSample(**data)
        loaded.append(sample)
    assert len(loaded) == 4
