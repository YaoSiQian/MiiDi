# Evaluation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full evaluation system: Judge track (J1/J2/J3), ~36 eval samples, single-command eval runner, E1/E2/E3 experiments, and documentation.

**Architecture:** Extend existing rule-track evaluator with LLM-as-judge dimensions. Create eval infrastructure (samples, runners, experiments) as a separate module. Document everything for competition submission.

**Tech Stack:** Python, pydantic v2, httpx (LLM calls), YAML (samples), pandas/numpy (analysis), pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-miidi-design.md` (§6-§8 for eval system)

## Global Constraints

- Python ≥3.11, pydantic v2
- LLM client: `src/miidi/llm/client.py` (dual backend: OpenAI + Zen)
- Eval core: `src/miidi/eval/` (axes, gates, score, context, style)
- Style packs: `skills/{pop,classical,jazz,lofi,touhou}/`
- All tests in `tests/` using pytest
- No new external dependencies beyond what's in pyproject.toml

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/miidi/eval/judge.py` | Judge track: J1/J2/J3 LLM-as-judge dimensions |
| `src/miidi/eval/composite.py` | Composite score: `0.6·R_rule + 0.4·mean(J1,J2,J3)` |
| `evals/__init__.py` | Package marker |
| `evals/samples/__init__.py` | Package marker |
| `evals/samples/pop_basic_01.yaml` through `pop_basic_04.yaml` | Pop basic prompts |
| `evals/samples/classical_basic_01.yaml` through `classical_basic_04.yaml` | Classical basic prompts |
| `evals/samples/jazz_basic_01.yaml` through `jazz_basic_04.yaml` | Jazz basic prompts |
| `evals/samples/lofi_basic_01.yaml` through `lofi_basic_04.yaml` | Lo-fi basic prompts |
| `evals/samples/touhou_basic_01.yaml` through `touhou_basic_04.yaml` | Touhou basic prompts |
| `evals/samples/constraint_01.yaml` through `constraint_08.yaml` | Constraint prompts |
| `evals/samples/hard_01.yaml` through `hard_06.yaml` | Hard prompts |
| `evals/samples/adversarial_01.yaml` through `adversarial_04.yaml` | Adversarial prompts |
| `evals/runners/__init__.py` | Package marker |
| `evals/runners/run_eval.py` | Single-command eval runner |
| `evals/experiments/__init__.py` | Package marker |
| `evals/experiments/e1_discrimination.py` | E1: good/medium/bad discrimination |
| `evals/experiments/e2_consistency.py` | E2: rule-track determinism + judge stability |
| `evals/experiments/e3_adversarial.py` | E3: cheat strategy detection |
| `evals/results/` | Output directory for results |
| `docs/evaluation.md` | Standalone eval method doc |
| `docs/report.md` | Full analysis report |
| `tests/test_judge.py` | Judge track tests |
| `tests/test_composite.py` | Composite score tests |
| `tests/test_eval_runner.py` | Eval runner tests |

### Modified Files

| File | Change |
|------|--------|
| `src/miidi/eval/__init__.py` | Export judge + composite |
| `src/miidi/eval/score.py` | Add composite score integration |
| `src/miidi/web/routes.py` | Add composite score to evaluate endpoint |
| `src/miidi/web/schemas.py` | Add composite score fields |
| `webapp/frontend/js/app.js` | Display composite + judge scores |
| `pyproject.toml` | Add pyyaml, pandas, numpy to dev deps |

---

## Task 1: Judge Track Core

**Files:**
- Create: `src/miidi/eval/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `Composition`, `StylePack`, `LLMClient`, `RuleReport`
- Produces: `JudgeReport` with `J1`, `J2`, `J3` scores + per_item + evidence

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judge.py
import pytest
from unittest.mock import MagicMock
from miidi.eval.judge import JudgeReport, evaluate_judge
from miidi.eval.score import RuleReport
from miidi.schema.model import Composition, Section, Track

def _make_comp():
    return Composition(
        meta={"title": "test", "bpm": 120, "time_signature": [4, 4],
              "key": {"tonic_pc": 0, "mode": "major"}},
        structure=[Section(name="verse", start_bar=0, bars=4)],
        harmony=[{"bar": 0, "dur_bars": 4.0, "symbol": "C"}],
        tracks=[Track(name="Lead", program=73, role="melody",
                      notes=[(0, 480, 60, 96), (480, 480, 64, 96)])],
    )

def test_judge_report_structure():
    report = JudgeReport(J1=80.0, J2=90.0, J3=70.0,
                         per_item={"J1": [], "J2": [], "J3": []},
                         evidence=[])
    d = report.to_dict()
    assert d["J1"] == 80.0
    assert d["J2"] == 90.0
    assert d["J3"] == 70.0
    assert "composite" not in d

def test_evaluate_judge_returns_report():
    client = MagicMock()
    client.respond_json.return_value = {
        "score": 75.0,
        "per_item": [{"item": "scale_adherence", "verdict": "yes", "evidence": "all notes in C major"}],
        "evidence": [{"track": "Lead", "bar": 0, "text": "scale adherence verified"}],
    }
    comp = _make_comp()
    rule_report = RuleReport(invalid=False, R_rule=65.0)
    report = evaluate_judge(comp, rule_report, client, "pop")
    assert isinstance(report, JudgeReport)
    assert 0 <= report.J1 <= 100
    assert 0 <= report.J2 <= 100
    assert 0 <= report.J3 <= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_judge.py -v`
Expected: FAIL with "cannot import name 'JudgeReport'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/miidi/eval/judge.py
from __future__ import annotations
from dataclasses import dataclass, field
from miidi.llm.client import LLMClient
from miidi.schema.model import Composition
from miidi.skills.loader import StylePack, load_style_pack

@dataclass(frozen=True)
class JudgeReport:
    J1: float  # Style adherence (0-100)
    J2: float  # Prompt following (0-100)
    J3: float  # Musicality (0-100)
    per_item: dict[str, list[dict]] = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "J1": round(self.J1, 2),
            "J2": round(self.J2, 2),
            "J3": round(self.J3, 2),
            "per_item": self.per_item,
            "evidence": self.evidence,
        }

def _j1_system(pack: StylePack) -> str:
    return (
        f"You are a music style expert evaluating {pack.name} music.\n"
        f"STYLE FEATURES TO CHECK:\n{pack.skill_md[:2000]}\n\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"...\", "
        "\"verdict\": \"yes|partial|no\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j1_user(comp_dict: dict) -> str:
    import json
    return f"COMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate style adherence."

def _j2_system() -> str:
    return (
        "You evaluate prompt following for music generation.\n"
        "Check: explicit requirements (BPM, instruments, key, duration) against actual.\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"...\", "
        "\"verdict\": \"satisfied|violated|unaddressed\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j2_user(comp_dict: dict, prompt: str) -> str:
    import json
    return f"PROMPT: {prompt}\n\nCOMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate prompt following."

def _j3_system() -> str:
    return (
        "You evaluate overall musicality of a MIDI composition.\n"
        "Rubric: 1=unplayable, 2=errors dense, 3=competent but flat, "
        "4=coherent with dynamics, 5=clear structure with memorable moments.\n"
        "Output JSON: {\"score\": 0-100, \"per_item\": [{\"item\": \"rubric\", "
        "\"verdict\": \"1-5\", \"evidence\": \"...\"}], "
        "\"evidence\": [{\"track\": \"...\", \"bar\": N, \"text\": \"...\"}]}"
    )

def _j3_user(comp_dict: dict, rule_summary: str) -> str:
    import json
    return f"RULE TRACK RESULTS:\n{rule_summary}\n\nCOMPOSITION:\n{json.dumps(comp_dict, indent=2)}\n\nEvaluate musicality."

def _normalize_score(raw: dict, key: str) -> float:
    score = raw.get("score", 50.0)
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return 50.0

def evaluate_judge(comp: Composition, rule_report, client: LLMClient,
                   style: str) -> JudgeReport:
    pack = load_style_pack(style)
    comp_dict = comp.model_dump()
    rule_summary = f"R_rule={rule_report.R_rule:.1f}" if hasattr(rule_report, 'R_rule') else "N/A"

    # J1: Style adherence
    raw_j1 = client.respond_json(_j1_system(pack), _j1_user(comp_dict))
    j1_score = _normalize_score(raw_j1, "J1")

    # J2: Prompt following
    raw_j2 = client.respond_json(_j2_system(), _j2_user(comp_dict, style))
    j2_score = _normalize_score(raw_j2, "J2")

    # J3: Musicality
    raw_j3 = client.respond_json(_j3_system(), _j3_user(comp_dict, rule_summary))
    j3_score = _normalize_score(raw_j3, "J3")

    all_evidence = []
    all_per_item = {}
    for name, raw in [("J1", raw_j1), ("J2", raw_j2), ("J3", raw_j3)]:
        all_per_item[name] = raw.get("per_item", [])
        all_evidence.extend(raw.get("evidence", []))

    return JudgeReport(J1=j1_score, J2=j2_score, J3=j3_score,
                       per_item=all_per_item, evidence=all_evidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_judge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/judge.py tests/test_judge.py
git commit -m "feat: add judge track J1/J2/J3 LLM-as-judge"
```

---

## Task 2: Composite Score

**Files:**
- Create: `src/miidi/eval/composite.py`
- Test: `tests/test_composite.py`

**Interfaces:**
- Consumes: `RuleReport`, `JudgeReport`
- Produces: `CompositeReport` with composite score + breakdown

- [ ] **Step 1: Write the failing test**

```python
# tests/test_composite.py
from miidi.eval.composite import CompositeReport, compute_composite
from miidi.eval.score import RuleReport
from miidi.eval.judge import JudgeReport

def test_composite_formula():
    rule = RuleReport(invalid=False, R_rule=80.0)
    judge = JudgeReport(J1=70.0, J2=90.0, J3=60.0)
    report = compute_composite(rule, judge)
    expected = 0.6 * 80.0 + 0.4 * ((70.0 + 90.0 + 60.0) / 3)
    assert abs(report.composite - expected) < 0.01
    assert report.R_rule == 80.0
    assert report.Judge_mean == (70.0 + 90.0 + 60.0) / 3

def test_composite_invalid_rule():
    rule = RuleReport(invalid=True, R_rule=0.0)
    judge = JudgeReport(J1=70.0, J2=90.0, J3=60.0)
    report = compute_composite(rule, judge)
    assert report.composite == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_composite.py -v`
Expected: FAIL with "cannot import name 'CompositeReport'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/miidi/eval/composite.py
from __future__ import annotations
from dataclasses import dataclass
from miidi.eval.score import RuleReport
from miidi.eval.judge import JudgeReport

@dataclass(frozen=True)
class CompositeReport:
    composite: float
    R_rule: float
    Judge_mean: float
    J1: float
    J2: float
    J3: float

    def to_dict(self) -> dict:
        return {
            "composite": round(self.composite, 2),
            "R_rule": round(self.R_rule, 2),
            "Judge_mean": round(self.Judge_mean, 2),
            "J1": round(self.J1, 2),
            "J2": round(self.J2, 2),
            "J3": round(self.J3, 2),
        }

def compute_composite(rule: RuleReport, judge: JudgeReport) -> CompositeReport:
    if rule.invalid:
        return CompositeReport(composite=0.0, R_rule=0.0,
                               Judge_mean=0.0, J1=judge.J1,
                               J2=judge.J2, J3=judge.J3)
    judge_mean = (judge.J1 + judge.J2 + judge.J3) / 3.0
    composite = 0.6 * rule.R_rule + 0.4 * judge_mean
    return CompositeReport(composite=composite, R_rule=rule.R_rule,
                           Judge_mean=judge_mean, J1=judge.J1,
                           J2=judge.J2, J3=judge.J3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_composite.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/miidi/eval/composite.py tests/test_composite.py
git commit -m "feat: add composite score formula"
```

---

## Task 3: Eval Sample Schema

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/samples/__init__.py`
- Create: `evals/samples/schema.py`
- Test: `tests/test_eval_samples.py`

**Interfaces:**
- Produces: `EvalSample` pydantic model for YAML validation

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_samples.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_samples.py -v`
Expected: FAIL with "cannot import name 'EvalSample'"

- [ ] **Step 3: Write minimal implementation**

```python
# evals/samples/schema.py
from __future__ import annotations
from pydantic import BaseModel, Field

class EvalSample(BaseModel):
    id: str
    style: str
    prompt: str
    constraints: dict = Field(default_factory=dict)
    expectations: dict = Field(default_factory=dict)

    @property
    def sample_type(self) -> str:
        if self.id.startswith("adversarial"):
            return "adversarial"
        if self.id.startswith("hard"):
            return "hard"
        if self.id.startswith("constraint"):
            return "constraint"
        return "basic"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_samples.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evals/__init__.py evals/samples/__init__.py evals/samples/schema.py tests/test_eval_samples.py
git commit -m "feat: add eval sample schema"
```

---

## Task 4: Create Basic Samples (20 files)

**Files:**
- Create: `evals/samples/pop_basic_01.yaml` through `pop_basic_04.yaml`
- Create: `evals/samples/classical_basic_01.yaml` through `classical_basic_04.yaml`
- Create: `evals/samples/jazz_basic_01.yaml` through `jazz_basic_04.yaml`
- Create: `evals/samples/lofi_basic_01.yaml` through `lofi_basic_04.yaml`
- Create: `evals/samples/touhou_basic_01.yaml` through `touhou_basic_04.yaml`
- Test: `tests/test_eval_samples.py` (add loading tests)

- [ ] **Step 1: Create pop basic samples**

```yaml
# evals/samples/pop_basic_01.yaml
id: pop_basic_01
style: pop
prompt: "A bright, upbeat pop song about the joy of a sunny morning walk"
expectations:
  style_features: ["four-on-the-floor kick", "syncopated melody", "I-V-vi-IV progression"]
  genre: "pop"

# evals/samples/pop_basic_02.yaml
id: pop_basic_02
style: pop
prompt: "A bittersweet pop ballad about saying goodbye to a friend moving abroad"
expectations:
  style_features: ["verse-chorus structure", "emotional dynamics", "clean production"]
  genre: "pop"

# evals/samples/pop_basic_03.yaml
style: pop
prompt: "A danceable pop track with a catchy hook, perfect for a summer playlist"
expectations:
  style_features: ["strong downbeat", "repetitive hook", "build-up to chorus"]
  genre: "pop"

# evals/samples/pop_basic_04.yaml
id: pop_basic_04
style: pop
prompt: "A mellow acoustic pop tune about finding peace in a quiet garden"
expectations:
  style_features: ["gentle rhythm", "warm harmony", "intimate feel"]
  genre: "pop"
```

- [ ] **Step 2: Create classical basic samples**

```yaml
# evals/samples/classical_basic_01.yaml
id: classical_basic_01
style: classical
prompt: "A serene adagio in C major, evoking a peaceful lake at dawn"
expectations:
  style_features: ["functional harmony", "voice leading", "no drums"]
  genre: "classical"

# evals/samples/classical_basic_02.yaml
id: classical_basic_02
style: classical
prompt: "A dramatic sonata-allegro movement with development and recapitulation"
expectations:
  style_features: ["sonata form", "thematic development", "cadential patterns"]
  genre: "classical"

# evals/samples/classical_basic_03.yaml
id: classical_basic_03
style: classical
prompt: "A graceful minuet in 3/4 time with a trio section"
expectations:
  style_features: ["triple meter", "binary form", "ornamental melody"]
  genre: "classical"

# evals/samples/classical_basic_04.yaml
id: classical_basic_04
style: classical
prompt: "A lively scherzo with rapid scales and playful dynamics"
expectations:
  style_features: ["fast tempo", "dynamic contrasts", "virtuosic passages"]
  genre: "classical"
```

- [ ] **Step 3: Create jazz basic samples**

```yaml
# evals/samples/jazz_basic_01.yaml
id: jazz_basic_01
style: jazz
prompt: "A relaxed bossa nova in Bb major with a flute melody"
expectations:
  style_features: ["bossa nova rhythm", "extended chords", "gentle swing"]
  genre: "jazz"

# evals/samples/jazz_basic_02.yaml
id: jazz_basic_02
style: jazz
prompt: "A hard bop blues in F, energetic with walking bass and ride cymbal"
expectations:
  style_features: ["blues form", "walking bass", "swing eighth notes"]
  genre: "jazz"

# evals/samples/jazz_basic_03.yaml
id: jazz_basic_03
style: jazz
prompt: "A cool jazz ballad, thoughtful and understated with muted trumpet"
expectations:
  style_features: ["slow tempo", "sparse texture", "modal harmony"]
  genre: "jazz"

# evals/samples/jazz_basic_04.yaml
id: jazz_basic_04
style: jazz
prompt: "A bebop showcase with rapid chord changes and virtuosic alto sax"
expectations:
  style_features: ["fast tempo", "ii-V-I progressions", "chromatic passing tones"]
  genre: "jazz"
```

- [ ] **Step 4: Create lofi basic samples**

```yaml
# evals/samples/lofi_basic_01.yaml
id: lofi_basic_01
style: lofi
prompt: "A dreamy lo-fi hip hop beat for studying, with vinyl crackle and soft piano"
expectations:
  style_features: ["slow tempo 70-90 BPM", "swing drums", "warm pads"]
  genre: "lofi"

# evals/samples/lofi_basic_02.yaml
id: lofi_basic_02
style: lofi
prompt: "A nostalgic lo-fi track with reversed samples and muted guitar"
expectations:
  style_features: ["chill vibe", "imperfect timing", "filtered sound"]
  genre: "lofi"

# evals/samples/lofi_basic_03.yaml
id: lofi_basic_03
style: lofi
prompt: "A rainy day lo-fi piece with rain sounds and melancholic Rhodes"
expectations:
  style_features: ["ambient texture", "simple harmony", "relaxed groove"]
  genre: "lofi"

# evals/samples/lofi_basic_04.yaml
id: lofi_basic_04
style: lofi
prompt: "An upbeat lo-fi track with funky bass and jazzy chords"
expectations:
  style_features: ["groove-oriented", "jazzy harmony", "head-nodding rhythm"]
  genre: "lofi"
```

- [ ] **Step 5: Create touhou basic samples**

```yaml
# evals/samples/touhou_basic_01.yaml
id: touhou_basic_01
style: touhou
prompt: "A high-energy Touhou-style arrangement with fast piano arpeggios and trumpet melody"
expectations:
  style_features: ["150-190 BPM", "dense piano", "soaring melody"]
  genre: "touhou"

# evals/samples/touhou_basic_02.yaml
id: touhou_basic_02
style: touhou
prompt: "A dramatic orchestral Touhou piece with choir and brass"
expectations:
  style_features: ["epic build", "layered orchestration", "emotional climax"]
  genre: "touhou"

# evals/samples/touhou_basic_03.yaml
id: touhou_basic_03
style: touhou
prompt: "A playful Touhou melody with bouncy rhythm and bright timbres"
expectations:
  style_features: ["catchy melody", "energetic drums", "bright piano"]
  genre: "touhou"

# evals/samples/touhou_basic_04.yaml
id: touhou_basic_04
style: touhou
prompt: "An intense Touhou battle theme with rapid-fire notes and driving bass"
expectations:
  style_features: ["high density", "aggressive drums", "virtuosic piano"]
  genre: "touhou"
```

- [ ] **Step 6: Add YAML loading tests**

```python
# tests/test_eval_samples.py (add to existing)
import yaml
from pathlib import Path
from evals.samples.schema import EvalSample

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
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_eval_samples.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add evals/samples/*_basic_*.yaml
git commit -m "feat: add 20 basic eval samples"
```

---

## Task 5: Create Constraint, Hard, and Adversarial Samples (16 files)

**Files:**
- Create: `evals/samples/constraint_01.yaml` through `constraint_08.yaml`
- Create: `evals/samples/hard_01.yaml` through `hard_06.yaml`
- Create: `evals/samples/adversarial_01.yaml` through `adversarial_04.yaml`

- [ ] **Step 1: Create constraint samples**

```yaml
# evals/samples/constraint_01.yaml
id: constraint_01
style: pop
prompt: "A pop song at exactly 120 BPM in the key of G major, 32 bars long"
constraints:
  bpm: 120
  key: "G major"
  duration_bars: 32
expectations:
  explicit_requirements: ["bpm=120", "key=G major", "duration=32 bars"]

# evals/samples/constraint_02.yaml
id: constraint_02
style: jazz
prompt: "A jazz piece featuring trumpet and piano, tempo 140 BPM, in Eb major"
constraints:
  bpm: 140
  key: "Eb major"
  instruments: ["trumpet", "piano"]
expectations:
  explicit_requirements: ["bpm=140", "key=Eb major", "instruments=trumpet+piano"]

# evals/samples/constraint_03.yaml
id: constraint_03
style: classical
prompt: "A classical string quartet piece in D minor, 48 bars, allegro tempo"
constraints:
  bpm: 140
  key: "D minor"
  duration_bars: 48
  instruments: ["strings"]
expectations:
  explicit_requirements: ["bpm=140", "key=D minor", "duration=48 bars"]

# evals/samples/constraint_04.yaml
id: constraint_04
style: lofi
prompt: "A lo-fi beat at 85 BPM in Ab major with vinyl texture"
constraints:
  bpm: 85
  key: "Ab major"
expectations:
  explicit_requirements: ["bpm=85", "key=Ab major"]

# evals/samples/constraint_05.yaml
id: constraint_05
style: touhou
prompt: "A Touhou arrangement at 170 BPM in B minor, featuring piano and drums"
constraints:
  bpm: 170
  key: "B minor"
  instruments: ["piano", "drums"]
expectations:
  explicit_requirements: ["bpm=170", "key=B minor"]

# evals/samples/constraint_06.yaml
id: constraint_06
style: pop
prompt: "A 16-bar pop intro with just piano and vocals, key of C major"
constraints:
  duration_bars: 16
  key: "C major"
  instruments: ["piano"]
expectations:
  explicit_requirements: ["duration=16 bars", "key=C major"]

# evals/samples/constraint_07.yaml
id: constraint_07
style: jazz
prompt: "A jazz waltz in 3/4 time at 120 BPM in F major"
constraints:
  bpm: 120
  key: "F major"
  time_signature: [3, 4]
expectations:
  explicit_requirements: ["bpm=120", "key=F major", "time=3/4"]

# evals/samples/constraint_08.yaml
id: constraint_08
style: lofi
prompt: "A lo-fi track at exactly 75 BPM, 64 bars, in C minor"
constraints:
  bpm: 75
  key: "C minor"
  duration_bars: 64
expectations:
  explicit_requirements: ["bpm=75", "key=C minor", "duration=64 bars"]
```

- [ ] **Step 2: Create hard samples**

```yaml
# evals/samples/hard_01.yaml
id: hard_01
style: jazz
prompt: "A full jazz piece using only ii-V-I progressions throughout all sections"
expectations:
  style_features: ["ii-V-I only", "jazz harmony", "voice leading"]
  challenge: "strict harmonic constraint"

# evals/samples/hard_02.yaml
id: hard_02
style: touhou
prompt: "A Touhou piece at 190 BPM with maximum note density in the chorus"
expectations:
  style_features: ["high BPM", "dense chorus", "virtuosic"]
  challenge: "extreme density"

# evals/samples/hard_03.yaml
id: hard_03
style: pop
prompt: "A pop song that modulates from C major to Eb major in the bridge"
expectations:
  style_features: ["modulation", "bridge section", "key change"]
  challenge: "key modulation"

# evals/samples/hard_04.yaml
id: hard_04
style: classical
prompt: "A fugue with 3 voices in G minor, demonstrating stretto and inversion"
expectations:
  style_features: ["fugal texture", "counterpoint", "development"]
  challenge: "contrapuntal writing"

# evals/samples/hard_05.yaml
id: hard_05
style: lofi
prompt: "A lo-fi track with complex jazz harmony (maj9, min11, altered dominants)"
expectations:
  style_features: ["extended chords", "lo-fi aesthetic", "jazzy"]
  challenge: "harmonic complexity"

# evals/samples/hard_06.yaml
id: hard_06
style: pop
prompt: "A minimal pop piece with only 4 bars and a single melody line"
expectations:
  style_features: ["minimal", "short form", "single voice"]
  challenge: "boundary value - minimal"
```

- [ ] **Step 3: Create adversarial samples**

```yaml
# evals/samples/adversarial_01.yaml
id: adversarial_01
style: pop
prompt: "Write a 300 BPM lullaby that is both extremely fast and very soothing"
expectations:
  contradiction: "high tempo vs soothing mood"
  expected_behavior: "graceful degradation or explanation"

# evals/samples/adversarial_02.yaml
id: adversarial_02
style: classical
prompt: "A classical piece in 3/4 and 4/4 time simultaneously"
expectations:
  contradiction: "conflicting time signatures"
  expected_behavior: "rejection or clarification"

# evals/samples/adversarial_03.yaml
id: adversarial_03
style: jazz
prompt: "A jazz piece that uses no seventh chords and has no swing feel"
expectations:
  contradiction: "jazz without defining features"
  expected_behavior: "adaptation or explanation"

# evals/samples/adversarial_04.yaml
id: adversarial_04
style: lofi
prompt: "A lo-fi track at 200 BPM with aggressive distorted guitars"
expectations:
  contradiction: "lo-fi aesthetic vs aggressive distortion"
  expected_behavior: "style mismatch handling"
```

- [ ] **Step 4: Add YAML loading tests**

```python
# tests/test_eval_samples.py (add to existing)
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
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_eval_samples.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add evals/samples/constraint_*.yaml evals/samples/hard_*.yaml evals/samples/adversarial_*.yaml
git commit -m "feat: add 16 constraint/hard/adversarial eval samples"
```

---

## Task 6: Eval Runner

**Files:**
- Create: `evals/runners/__init__.py`
- Create: `evals/runners/run_eval.py`
- Test: `tests/test_eval_runner.py`

**Interfaces:**
- Consumes: `EvalSample`, `LLMClient`, `StylePack`
- Produces: CSV + Markdown results in `evals/results/`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_runner.py
from unittest.mock import MagicMock, patch
from evals.runners.run_eval import EvalResult, run_single_sample

def test_eval_result_to_dict():
    from evals.runners.run_eval import EvalResult
    result = EvalResult(
        sample_id="pop_basic_01",
        style="pop",
        R_rule=75.0, J1=80.0, J2=85.0, J3=70.0, composite=76.0,
        note_count=120, track_count=4, duration_bars=32,
    )
    d = result.to_dict()
    assert d["sample_id"] == "pop_basic_01"
    assert d["composite"] == 76.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_runner.py -v`
Expected: FAIL with "cannot import name 'EvalResult'"

- [ ] **Step 3: Write minimal implementation**

```python
# evals/runners/run_eval.py
from __future__ import annotations
import csv
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from miidi.llm.client import LLMClient, load_config
from miidi.pipeline.orchestrator import run_pipeline
from miidi.eval.score import evaluate_rules
from miidi.eval.judge import evaluate_judge
from miidi.eval.composite import compute_composite
from miidi.eval.style import StyleDefaults
from miidi.skills.loader import load_style_pack
from evals.samples.schema import EvalSample
import yaml

@dataclass
class EvalResult:
    sample_id: str
    style: str
    R_rule: float = 0.0
    J1: float = 0.0
    J2: float = 0.0
    J3: float = 0.0
    composite: float = 0.0
    note_count: int = 0
    track_count: int = 0
    duration_bars: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

def run_single_sample(sample: EvalSample, client: LLMClient,
                      out_dir: Path) -> EvalResult:
    result = EvalResult(sample_id=sample.id, style=sample.style)
    try:
        pack = load_style_pack(sample.style)
        pipeline_result = run_pipeline(
            sample.prompt, sample.style, client,
            out_dir=out_dir, store=None)
        if pipeline_result.comp is None:
            result.error = "generation failed"
            return result
        comp = pipeline_result.comp
        result.note_count = sum(len(t.notes) for t in comp.tracks)
        result.track_count = len(comp.tracks)
        result.duration_bars = int(comp.total_bars())

        rule_report = evaluate_rules(comp, pack.defaults)
        result.R_rule = rule_report.R_rule

        if not rule_report.invalid:
            judge_report = evaluate_judge(comp, rule_report, client, sample.style)
            result.J1 = judge_report.J1
            result.J2 = judge_report.J2
            result.J3 = judge_report.J3
            composite = compute_composite(rule_report, judge_report)
            result.composite = composite.composite
        else:
            result.composite = 0.0
            result.error = "invalid composition"
    except Exception as exc:
        result.error = str(exc)[:200]
    return result

def run_eval(samples_dir: Path, out_dir: Path,
             client: LLMClient | None = None) -> list[EvalResult]:
    if client is None:
        client = LLMClient(load_config())
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for f in sorted(samples_dir.glob("*.yaml")):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        samples.append(EvalSample(**data))
    results = []
    for i, sample in enumerate(samples):
        print(f"[{i+1}/{len(samples)}] {sample.id} ({sample.style})")
        result = run_single_sample(sample, client, out_dir / sample.id)
        results.append(result)
    _write_csv(results, out_dir / "results.csv")
    _write_markdown(results, out_dir / "results.md")
    return results

def _write_csv(results: list[EvalResult], path: Path):
    if not results:
        return
    fieldnames = list(results[0].to_dict().keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())

def _write_markdown(results: list[EvalResult], path: Path):
    lines = ["# Evaluation Results\n"]
    lines.append("| Sample | Style | R_rule | J1 | J2 | J3 | Composite | Error |")
    lines.append("|--------|-------|--------|-----|-----|-----|-----------|-------|")
    for r in results:
        err = r.error[:30] if r.error else ""
        lines.append(f"| {r.sample_id} | {r.style} | {r.R_rule:.1f} | "
                     f"{r.J1:.1f} | {r.J2:.1f} | {r.J3:.1f} | "
                     f"{r.composite:.1f} | {err} |")
    path.write_text("\n".join(lines))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run_eval(args.samples, args.out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evals/runners/__init__.py evals/runners/run_eval.py tests/test_eval_runner.py
git commit -m "feat: add eval runner with CSV/Markdown output"
```

---

## Task 7: E1 Discrimination Experiment

**Files:**
- Create: `evals/experiments/__init__.py`
- Create: `evals/experiments/e1_discrimination.py`
- Test: `tests/test_experiments.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experiments.py
from evals.experiments.e1_discrimination import DegradationOp, degrade_composition

def test_degrade_sanitize_pitch():
    from miidi.schema.model import Composition, Section, Track
    comp = Composition(
        meta={"title": "test", "bpm": 120, "time_signature": [4, 4],
              "key": {"tonic_pc": 0, "mode": "major"}},
        structure=[Section(name="verse", start_bar=0, bars=4)],
        tracks=[Track(name="Lead", program=73, role="melody",
                      notes=[(0, 480, 60, 96), (480, 480, 64, 96)])],
    )
    degraded = degrade_composition(comp, DegradationOp.SCATTER_PITCH)
    assert degraded is not None
    assert len(degraded.tracks[0].notes) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_experiments.py -v`
Expected: FAIL with "cannot import name 'DegradationOp'"

- [ ] **Step 3: Write minimal implementation**

```python
# evals/experiments/e1_discrimination.py
from __future__ import annotations
import random
from enum import Enum
from miidi.schema.model import Composition, Track

class DegradationOp(Enum):
    SCATTER_PITCH = "scatter_pitch"
    REMOVE_TRACK = "remove_track"
    SCATTER_ONSET = "scatter_onset"
    REPEAT_FIRST_BAR = "repeat_first_bar"

def degrade_composition(comp: Composition, op: DegradationOp,
                        seed: int = 42) -> Composition:
    rng = random.Random(seed)
    new_tracks = []
    for track in comp.tracks:
        new_notes = list(track.notes)
        if op == DegradationOp.SCATTER_PITCH:
            new_notes = [(o, d, rng.randint(48, 84), v) for o, d, p, v in new_notes]
        elif op == DegradationOp.SCATTER_ONSET:
            new_notes = [(o + rng.randint(-60, 60), d, p, v) for o, d, p, v in new_notes]
        elif op == DegradationOp.REPEAT_FIRST_BAR:
            bar_ticks = comp.bar_ticks
            first_bar_notes = [n for n in new_notes if n[0] < bar_ticks]
            repeated = []
            total_bars = int(comp.total_bars())
            for bar in range(total_bars):
                for onset, dur, pitch, vel in first_bar_notes:
                    new_onset = onset + bar * bar_ticks
                    if new_onset + dur <= total_bars * bar_ticks:
                        repeated.append((new_onset, dur, pitch, vel))
            new_notes = repeated
        new_tracks.append(track.model_copy(update={"notes": new_notes}))

    if op == DegradationOp.REMOVE_TRACK and len(new_tracks) > 1:
        new_tracks = new_tracks[:-1]

    return comp.model_copy(update={"tracks": new_tracks})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_experiments.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evals/experiments/__init__.py evals/experiments/e1_discrimination.py tests/test_experiments.py
git commit -m "feat: add E1 discrimination experiment with degradation ops"
```

---

## Task 8: E2 Consistency Experiment

**Files:**
- Create: `evals/experiments/e2_consistency.py`

- [ ] **Step 1: Write the implementation**

```python
# evals/experiments/e2_consistency.py
from __future__ import annotations
from dataclasses import dataclass
from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.schema.model import Composition

@dataclass
class ConsistencyResult:
    rule_deterministic: bool
    rule_range: dict[str, float]
    judge_stability: dict[str, float] | None = None

def check_rule_determinism(comp: Composition, defaults: StyleDefaults,
                           runs: int = 3) -> ConsistencyResult:
    scores = []
    for _ in range(runs):
        report = evaluate_rules(comp, defaults)
        scores.append(report.R_rule)
    rule_range = {
        "min": min(scores),
        "max": max(scores),
        "range": max(scores) - min(scores),
        "std": (sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)) ** 0.5,
    }
    return ConsistencyResult(
        rule_deterministic=rule_range["range"] == 0.0,
        rule_range=rule_range,
    )
```

- [ ] **Step 2: Commit**

```bash
git add evals/experiments/e2_consistency.py
git commit -m "feat: add E2 consistency experiment"
```

---

## Task 9: E3 Adversarial Experiment

**Files:**
- Create: `evals/experiments/e3_adversarial.py`

- [ ] **Step 1: Write the implementation**

```python
# evals/experiments/e3_adversarial.py
from __future__ import annotations
from dataclasses import dataclass
from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.schema.model import Composition
from evals.experiments.e1_discrimination import DegradationOp, degrade_composition

@dataclass
class AdversarialResult:
    original_score: float
    degraded_scores: dict[str, float]
    all_detected: bool  # All degraded <= original

def run_adversarial(comp: Composition, defaults: StyleDefaults) -> AdversarialResult:
    original = evaluate_rules(comp, defaults)
    degraded_scores = {}
    for op in DegradationOp:
        degraded = degrade_composition(comp, op)
        report = evaluate_rules(degraded, defaults)
        degraded_scores[op.value] = report.R_rule
    all_detected = all(v <= original.R_rule for v in degraded_scores.values())
    return AdversarialResult(
        original_score=original.R_rule,
        degraded_scores=degraded_scores,
        all_detected=all_detected,
    )
```

- [ ] **Step 2: Commit**

```bash
git add evals/experiments/e3_adversarial.py
git commit -m "feat: add E3 adversarial experiment"
```

---

## Task 10: Update Web Routes with Composite Score

**Files:**
- Modify: `src/miidi/web/routes.py:211-229`
- Modify: `src/miidi/web/schemas.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Update schemas**

```python
# src/miidi/web/schemas.py (add to EvaluateResponse)
class EvaluateResponse(BaseModel):
    report: dict
    composite: dict | None = None
```

- [ ] **Step 2: Update route to include composite**

```python
# src/miidi/web/routes.py (modify evaluate endpoint)
@router.post("/sessions/{sid}/evaluate")
async def evaluate(sid: str) -> EvaluateResponse:
    _store.session_meta(sid)
    latest = _store.latest(sid)
    ver = _store.load_version(sid, latest)
    from miidi.schema.model import Composition
    comp = Composition(**ver.get("composition", {}))
    style = ver.get("style", "touhou")
    pack = load_style_pack(style)
    report = evaluate_rules(comp, pack.defaults)
    composite_dict = None
    if not report.invalid:
        try:
            from miidi.eval.judge import evaluate_judge
            from miidi.eval.composite import compute_composite
            from miidi.llm.client import load_config, LLMClient
            client = LLMClient(load_config())
            judge = evaluate_judge(comp, report, client, style)
            comp_report = compute_composite(report, judge)
            composite_dict = comp_report.to_dict()
            client.close()
        except Exception:
            pass
    return EvaluateResponse(report=report.to_dict(), composite=composite_dict)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_web.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/miidi/web/routes.py src/miidi/web/schemas.py
git commit -m "feat: add composite score to evaluate endpoint"
```

---

## Task 11: Update Frontend with Composite Display

**Files:**
- Modify: `webapp/frontend/js/app.js`

- [ ] **Step 1: Add composite display to evaluator window**

```javascript
// In app.js, after displaying R_rule scores, add:
if (data.composite) {
    const compDiv = document.createElement('div');
    compDiv.className = 'eval-composite';
    compDiv.innerHTML = `
        <h3>Composite Score</h3>
        <div class="composite-score">${data.composite.composite.toFixed(1)}</div>
        <div class="composite-breakdown">
            R_rule: ${data.composite.R_rule.toFixed(1)} (60%) |
            Judge: ${data.composite.Judge_mean.toFixed(1)} (40%)
        </div>
        <div class="judge-scores">
            J1 Style: ${data.composite.J1.toFixed(1)} |
            J2 Prompt: ${data.composite.J2.toFixed(1)} |
            J3 Musical: ${data.composite.J3.toFixed(1)}
        </div>
    `;
    evalContent.appendChild(compDiv);
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/frontend/js/app.js
git commit -m "feat: display composite score in evaluator window"
```

---

## Task 12: Documentation

**Files:**
- Create: `docs/evaluation.md`
- Create: `docs/report.md`

- [ ] **Step 1: Create evaluation.md**

```markdown
# MiiDi Evaluation Method

## Overview

MiiDi uses a dual-track evaluation system:

1. **Rule Track** (deterministic): 6 axes + 4 gates → R_rule ∈ [0,100]
2. **Judge Track** (LLM-as-judge): 3 dimensions → J1, J2, J3 ∈ [0,100]

Composite: `0.6·R_rule + 0.4·mean(J1,J2,J3)`

## Rule Track Axes

| Axis | Weight | What it measures |
|------|--------|-----------------|
| A1 Format | gate | validate() pass/fail |
| A2 Harmony | 0.30 | Scale adherence, chord support, cluster rate |
| A3 Voice | 0.20 | Range fit, parallel motion, leap rate |
| A4 Rhythm | 0.20 | Grid adherence, density, drum patterns |
| A5 Structure | 0.20 | Coverage, similarity, motif recall |
| A6 Dynamics | 0.10 | Velocity spread, directionality |

## Anti-Degeneration Gates

- G_repetition: n-gram self-copy rate
- G_density: extreme density penalty
- G_balance: track content imbalance
- G_spread: fake register width

## Judge Track Dimensions

| Dimension | What it checks | Rubric |
|-----------|---------------|--------|
| J1 Style | Adherence to style features | yes/partial/no per feature |
| J2 Prompt | Following explicit requirements | satisfied/violated/unaddressed |
| J3 Musicality | Overall musical quality | 1-5 anchor rubric |

## Experiments

- E1 Discrimination: good/medium/bad tiers
- E2 Consistency: rule determinism + judge stability
- E3 Adversarial: cheat strategy detection
```

- [ ] **Step 2: Create report.md**

```markdown
# MiiDi Analysis Report

## Scenario

Symbolic music generation (MIDI) — no single correct answer, evaluation must be self-designed.

## Architecture

Layered pipeline: Plan → Core → Arrange → Coordinate → Review

## Evaluation Dimensions

Dual-track: rule (objective) + judge (subjective)

## Conclusions

[To be filled after running experiments]

## Failure Modes

[To be filled after analyzing results]

## Model Information

LLM: OpenAI-compatible API (Zen fallback: hy3-free)

## Limitations

- Same model for generation and judging (self-preference risk)
- Single-person annotation (statistical limitations)
- Symbolic metrics ≠ listening quality
```

- [ ] **Step 3: Commit**

```bash
git add docs/evaluation.md docs/report.md
git commit -m "docs: add evaluation method and analysis report"
```

---

## Task 13: Add PyYAML Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pyyaml to dev dependencies**

```toml
# pyproject.toml (add to [project.optional-dependencies])
dev = ["pytest>=8.0", "pyyaml>=6.0"]
```

- [ ] **Step 2: Install and commit**

```bash
pip install pyyaml
git add pyproject.toml
git commit -m "deps: add pyyaml for eval samples"
```

---

## Task 14: Final Verification

**Files:**
- Run all tests
- Verify eval runner works

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run eval on 3 samples (smoke test)**

```bash
python -m evals.runners.run_eval \
  --samples evals/samples/ \
  --out evals/results/ \
  --limit 3
```

- [ ] **Step 3: Verify results files exist**

```bash
ls -la evals/results/
# Should contain: results.csv, results.md
```

- [ ] **Step 4: Commit**

```bash
git add evals/results/
git commit -m "chore: add initial eval results"
```

---

## Summary

| Task | Description | Files Created |
|------|-------------|---------------|
| 1 | Judge Track Core | judge.py, test_judge.py |
| 2 | Composite Score | composite.py, test_composite.py |
| 3 | Eval Sample Schema | schema.py, test_eval_samples.py |
| 4 | Basic Samples (20) | 20 YAML files |
| 5 | Constraint/Hard/Adversarial (16) | 16 YAML files |
| 6 | Eval Runner | run_eval.py, test_eval_runner.py |
| 7 | E1 Discrimination | e1_discrimination.py |
| 8 | E2 Consistency | e2_consistency.py |
| 9 | E3 Adversarial | e3_adversarial.py |
| 10 | Web Routes Update | routes.py, schemas.py |
| 11 | Frontend Update | app.js |
| 12 | Documentation | evaluation.md, report.md |
| 13 | Dependencies | pyproject.toml |
| 14 | Final Verification | - |

**Total new files:** ~45
**Total modified files:** ~5
**Estimated implementation time:** 2-3 hours
