# MiiDi Plan 2: Generation Pipeline (LLM Client + Style Skills + Four-Stage Pipeline + Sessions)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generation side of miidi on top of the landed kernel (main@bdc43f6): an OpenAI Responses-protocol LLM client, five style skill packs, the Plan→Compose→Self-review→Render pipeline, session storage with revision, and a minimal CLI.

**Architecture:** `miidi.llm` is the only network-touching module and is fully injectable (transport callable) so every other layer is testable with fake clients. `miidi.pipeline` stages are pure functions of (client, pack, inputs); the orchestrator sequences them. Style packs are data under repo-root `skills/<name>/`; their `defaults.json` feeds kernel `StyleDefaults`.

**Tech Stack:** Python ≥3.11, httpx (already in pyproject `[judge]` extra — move to core deps), pydantic v2, existing kernel APIs.

**Spec:** `docs/superpowers/specs/2026-08-22-miidi-design.md` (§5 生成流水线与曲风 Skills, §5.4 LLM 客户端, §9.1 会话)

## Global Constraints

- Kernel APIs are FROZEN as landed on main; import, never modify: `normalize_raw`, `validate_composition`, `Composition/Track/Meta/Section/ChordSpan`, `PPQ`, `generate_midi`, `midi_to_wav/AudioUnavailableError`, `evaluate_rules/RuleReport`, `StyleDefaults`, `parse_chord`.
- No RNG anywhere in pipeline code. Determinism: same client responses + same prompt ⇒ identical Composition.
- LLM config ONLY from environment: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME` (spec §0.3).
- Every LLM call returns JSON; malformed output flows through repair-retry (≤2) then explicit failure — never silent defaults.
- No comments in code unless citing spec.
- Conventional commits; run tests from repo root.

---

### Task 1: LLM client (Responses protocol)

**Files:**
- Modify: `pyproject.toml` (move httpx into core dependencies)
- Create: `src/miidi/llm/__init__.py`, `src/miidi/llm/client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Produces:
  - `LLMConfigError(RuntimeError)`; `load_config(env: Mapping[str,str] | None = None) -> LLMConfig` reading `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME` (missing any → `LLMConfigError`)
  - `LLMConfig(base_url, api_key, model, timeout_s: float = 120.0, max_retries: int = 2)`
  - `LLMError(RuntimeError)`
  - `extract_json(text: str) -> dict` — strips ``` fences, takes the first balanced `{...}` block, `json.loads`; raises `LLMError` on failure
  - `LLMClient(config, transport=None)` — transport is an httpx transport (tests inject `httpx.MockTransport`)
  - `.respond_json(system: str, user: str, temperature: float = 0.0, name: str = "response") -> dict`:
    POST `{base_url}/responses` body `{"model", "input": [{"role":"system","content":[{"type":"input_text","text":system}]},{"role":"user","content":[{"type":"input_text","text":user}]}], "temperature": temperature}`.
    Retry on 429/5xx/timeouts with backoff `0.5 * 3**attempt`; raise `LLMError` after retries. Parse reply text via `_reply_text(data)`: try top-level `"output_text"` (str), else walk `data["output"][*]["content"][*]` collecting `text` where `type=="output_text"`. Then `extract_json`.
    If the endpoint answers 400 with `"json_schema"` unsupported semantics — NOT implemented in v1; we always send plain requests (structured output is a Plan-4 experiment knob). Keep the request schema-free.

- [ ] **Step 1: Write failing tests**

`tests/test_llm_client.py`:
```python
import json

import httpx
import pytest

from miidi.llm.client import (
    LLMClient, LLMConfig, LLMConfigError, extract_json, load_config,
)


def make_config(**kw):
    return LLMConfig(base_url="http://fake/v1", api_key="k", model="m", **kw)


def responder(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)
    return handler


def ok_payload(text):
    return {"output": [{"type": "message",
                        "content": [{"type": "output_text", "text": text}]}]}


def test_load_config_from_env():
    cfg = load_config({"OPENAI_BASE_URL": "u", "OPENAI_API_KEY": "k", "MODEL_NAME": "m"})
    assert (cfg.base_url, cfg.api_key, cfg.model) == ("u", "k", "m")


@pytest.mark.parametrize("missing", ["OPENAI_BASE_URL", "OPENAI_API_KEY", "MODEL_NAME"])
def test_load_config_missing_key_raises(missing):
    env = {"OPENAI_BASE_URL": "u", "OPENAI_API_KEY": "k", "MODEL_NAME": "m"}
    del env[missing]
    with pytest.raises(LLMConfigError):
        load_config(env)


def test_extract_json_plain_and_fenced():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"a": {"b": 2}} suffix') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_respond_json_roundtrip():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_payload('{"notes": [[0, 480, 60, 96]]}'))

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    out = client.respond_json("sys", "usr")
    assert out == {"notes": [[0, 480, 60, 96]]}
    body = seen["body"]
    assert body["model"] == "m"
    assert body["input"][0]["role"] == "system"
    assert body["input"][1]["content"][0]["text"] == "usr"


def test_output_text_shortcut():
    def handler(request):
        return httpx.Response(200, json={"output_text": '{"x": 9}'})

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    assert client.respond_json("s", "u") == {"x": 9}


def test_retry_on_500_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=ok_payload("{}"))

    client = LLMClient(make_config(max_retries=2), transport=httpx.MockTransport(handler))
    assert client.respond_json("s", "u") == {}
    assert calls["n"] == 2


def test_exhausted_retries_raise():
    def handler(request):
        return httpx.Response(503, json={"error": "down"})

    client = LLMClient(make_config(max_retries=1), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.respond_json("s", "u")


def test_garbage_reply_raises_llm_error():
    def handler(request):
        return httpx.Response(200, json=ok_payload("not json"))

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.respond_json("s", "u")
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: FAIL ImportError

- [ ] **Step 3: Implement**

Modify `pyproject.toml`: move `"httpx>=0.27"` from `[project.optional-dependencies].judge` into core `dependencies` (leave the judge extra present but empty of httpx, or remove the judge extra entirely — choose removing it; nothing references it yet).

`src/miidi/llm/__init__.py`: empty file.

`src/miidi/llm/client.py`:
```python
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Mapping

import httpx


class LLMConfigError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 120.0
    max_retries: int = 2


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    e = os.environ if env is None else env
    missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "MODEL_NAME") if not e.get(k)]
    if missing:
        raise LLMConfigError(f"missing env vars: {', '.join(missing)}")
    return LLMConfig(base_url=e["OPENAI_BASE_URL"], api_key=e["OPENAI_API_KEY"],
                     model=e["MODEL_NAME"])


def extract_json(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    start = s.find("{")
    if start < 0:
        raise LLMError(f"no JSON object in reply: {text[:120]!r}")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                chunk = s[start:i + 1]
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"invalid JSON in reply: {exc}") from exc
    raise LLMError("unbalanced JSON object in reply")


def _reply_text(data: dict) -> str:
    t = data.get("output_text")
    if isinstance(t, str) and t.strip():
        return t
    parts: list[str] = []
    for item in data.get("output", []):
        for c in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(c, dict) and c.get("type") == "output_text":
                parts.append(c.get("text", ""))
    if not parts:
        raise LLMError(f"no output text in response keys={list(data)}")
    return "".join(parts)


class LLMClient:
    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        kwargs: dict = {"timeout": config.timeout_s}
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.Client(**kwargs)

    def close(self) -> None:
        self._http.close()

    def respond_json(self, system: str, user: str, temperature: float = 0.0,
                     name: str = "response") -> dict:
        payload = {
            "model": self.config.model,
            "input": [
                {"role": "system",
                 "content": [{"type": "input_text", "text": system}]},
                {"role": "user",
                 "content": [{"type": "input_text", "text": user}]},
            ],
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._http.post(
                    f"{self.config.base_url.rstrip('/')}/responses",
                    json=payload, headers=headers)
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                return extract_json(_reply_text(resp.json()))
            except (LLMError, httpx.HTTPError) as exc:
                last_error = exc
                retryable = isinstance(exc, httpx.HTTPError)
                status = getattr(exc, "args", [""])[0] if isinstance(exc, LLMError) else ""
                if isinstance(exc, LLMError) and not str(status).startswith(("HTTP 429", "HTTP 5")):
                    break
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (3 ** attempt))
        raise LLMError(f"LLM call failed after retries: {last_error}") from last_error
```

Note on retry classification: non-retryable 4xx (e.g. 401) must fail fast — the `startswith(("HTTP 429", "HTTP 5"))` check implements that; adjust the message prefix contract if you refactor.

- [ ] **Step 4: Verify pass + full suite**

Run: `python -m pytest tests/test_llm_client.py -v && python -m pytest tests/ -q`
Expected: new tests PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/miidi/llm tests/test_llm_client.py
git commit -m "feat: Responses-protocol LLM client with retries and JSON extraction"
```

---
### Task 2: Style-pack loader

**Files:**
- Create: `src/miidi/skills/__init__.py`, `src/miidi/skills/loader.py`
- Test: `tests/test_skills_loader.py`

**Interfaces:**
- Consumes: `StyleDefaults` from `miidi.eval.style`.
- Produces:
  - `StylePack(name: str, skill_md: str, instruments_md: str, harmony_md: str, rhythm_md: str, defaults: StyleDefaults)`
  - `load_style_pack(name: str, skills_dir: str | Path | None = None) -> StylePack` — default dir resolution: `$MIIDI_SKILLS_DIR` env if set, else `<repo-root>/skills`; raises `FileNotFoundError` on unknown style
  - `available_styles(skills_dir=None) -> list[str]` — sorted directory names containing `defaults.json`
  - `defaults.json` schema (all keys required): `{"bpm_range": [lo, hi], "density_ref": {"__global__": [lo, hi], "<role>": [...]...}, "swing_offsets": [], "drum_patterns": {"kick"/"snare"/"hat"?: []}}` → mapped to `StyleDefaults(bpm_range=tuple, density_ref={k: tuple(v)}, swing_offsets=list, drum_patterns=as-is, section_vocab=kernel default)`
  - Malformed defaults.json → `ValueError` naming the style and key.

- [ ] **Step 1: Write failing tests**

`tests/test_skills_loader.py`:
```python
import json

import pytest

from miidi.eval.style import StyleDefaults
from miidi.skills.loader import available_styles, load_style_pack


@pytest.fixture()
def pack_dir(tmp_path):
    root = tmp_path / "skills"
    style = root / "teststyle"
    style.mkdir(parents=True)
    for f in ("SKILL.md", "instruments.md", "harmony.md", "rhythm.md"):
        (style / f).write_text(f"# {f}\n")
    (style / "defaults.json").write_text(json.dumps({
        "bpm_range": [70, 140],
        "density_ref": {"__global__": [4, 24], "melody": [2, 10]},
        "swing_offsets": [200],
        "drum_patterns": {"kick": [0]},
    }))
    return root


def test_load_pack_maps_defaults(pack_dir):
    pack = load_style_pack("teststyle", skills_dir=pack_dir)
    assert pack.name == "teststyle"
    assert isinstance(pack.defaults, StyleDefaults)
    assert pack.defaults.bpm_range == (70.0, 140.0)
    assert pack.defaults.density_ref["melody"] == (2, 10)
    assert pack.defaults.swing_offsets == [200]
    assert pack.skill_md.startswith("# SKILL.md")


def test_missing_file_raises(pack_dir):
    (pack_dir / "teststyle" / "rhythm.md").unlink()
    with pytest.raises(FileNotFoundError):
        load_style_pack("teststyle", skills_dir=pack_dir)


def test_unknown_style_raises(pack_dir):
    with pytest.raises(FileNotFoundError):
        load_style_pack("nope", skills_dir=pack_dir)


def test_available_styles_sorted(pack_dir):
    assert available_styles(skills_dir=pack_dir) == ["teststyle"]


def test_malformed_defaults_raise(pack_dir):
    (pack_dir / "teststyle" / "defaults.json").write_text('{"bpm_range": [1]}')
    with pytest.raises(ValueError):
        load_style_pack("teststyle", skills_dir=pack_dir)


def test_env_var_resolution(pack_dir, monkeypatch):
    monkeypatch.setenv("MIIDI_SKILLS_DIR", str(pack_dir))
    assert load_style_pack("teststyle").name == "teststyle"
```

- [ ] **Step 2: Verify failure** — Run: `python -m pytest tests/test_skills_loader.py -v`, expect FAIL ImportError.

- [ ] **Step 3: Implement**

`src/miidi/skills/__init__.py`: empty file.

`src/miidi/skills/loader.py`:
```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from miidi.eval.style import StyleDefaults

_REQUIRED_FILES = ("SKILL.md", "instruments.md", "harmony.md", "rhythm.md",
                   "defaults.json")


@dataclass(frozen=True)
class StylePack:
    name: str
    skill_md: str
    instruments_md: str
    harmony_md: str
    rhythm_md: str
    defaults: StyleDefaults


def _default_dir() -> Path:
    env = os.environ.get("MIIDI_SKILLS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "skills"


def _parse_defaults(name: str, raw: dict) -> StyleDefaults:
    try:
        density = {k: (float(v[0]), float(v[1])) for k, v in raw["density_ref"].items()}
        return StyleDefaults(
            bpm_range=(float(raw["bpm_range"][0]), float(raw["bpm_range"][1])),
            density_ref=density,
            swing_offsets=[int(x) for x in raw.get("swing_offsets", [])],
            drum_patterns={k: [int(x) for x in v]
                           for k, v in raw.get("drum_patterns", {}).items()},
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"style {name!r}: malformed defaults.json ({exc})") from exc


def load_style_pack(name: str, skills_dir=None) -> StylePack:
    root = Path(skills_dir) if skills_dir else _default_dir()
    style_dir = root / name
    if not style_dir.is_dir():
        raise FileNotFoundError(f"unknown style {name!r} under {root}")
    texts = {}
    for f in _REQUIRED_FILES:
        p = style_dir / f
        if not p.is_file():
            raise FileNotFoundError(f"style {name!r}: missing {f}")
        texts[f] = p.read_text(encoding="utf-8")
    try:
        raw = json.loads(texts["defaults.json"])
    except json.JSONDecodeError as exc:
        raise ValueError(f"style {name!r}: defaults.json invalid JSON ({exc})") from exc
    return StylePack(name=name,
                     skill_md=texts["SKILL.md"],
                     instruments_md=texts["instruments.md"],
                     harmony_md=texts["harmony.md"],
                     rhythm_md=texts["rhythm.md"],
                     defaults=_parse_defaults(name, raw))


def available_styles(skills_dir=None) -> list[str]:
    root = Path(skills_dir) if skills_dir else _default_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and (p / "defaults.json").is_file())
```

Note: `parents[3]` from `src/miidi/skills/loader.py` lands at repo root (`src/miidi/skills/loader.py` → parents[0]=skills, [1]=miidi, [2]=src, [3]=repo). Editable install keeps this valid.

- [ ] **Step 4: Verify pass + suite** — `python -m pytest tests/test_skills_loader.py tests/ -q` → green.
- [ ] **Step 5: Commit**

```bash
git add src/miidi/skills tests/test_skills_loader.py
git commit -m "feat: style-pack loader feeding kernel StyleDefaults"
```

---

### Task 3: Five style packs (data authoring)

**Files:**
- Create: `skills/{pop,classical,jazz,lofi,touhou}/{SKILL.md,instruments.md,harmony.md,rhythm.md,defaults.json}` (25 files)
- Test: `tests/test_style_packs.py`

**Content contract.** Every pack MUST satisfy this structure (tests enforce it mechanically):

`SKILL.md` — headings exactly: `# <Style Name> Style`, `## Identity`, `## Workflow`, `## Output Rules`. Identity ≤5 sentences describing the aesthetic. Workflow lists which of the other three files each pipeline stage should read. Output Rules repeat the JSON-only contract and tick-grid rules (onsets integer ticks, ppq=480, rests are gaps, chords = same-onset duplicates, velocity 1-127 expressive not constant).

`instruments.md` — heading `# Instrumentation`; a table `| role | GM program | name | register note |` with ≥3 rows covering at minimum one melody, one bass, one harmonic-role instrument; plus a paragraph on what to avoid.

`harmony.md` — headings `# Harmony Vocabulary`, `## Characteristic Progressions`, `## Cadences`. Must enumerate ≥6 chord symbols usable verbatim by the planner (symbols MUST parse with the kernel parser: C Am F G7 Dm7 Bm7b5 ... — no maj9/13/11, no slash chords), ≥2 named progressions using those symbols, cadence guidance.

`rhythm.md` — headings `# Rhythmic Feel`, `## Drum Patterns`, `## Grid Notes`. Drum Patterns must present the SAME patterns encoded in defaults.json as readable grids (16-step rows). Grid Notes state subdivision policy incl. swing offsets if any.

`defaults.json` values per style (binding numbers):

| key | pop | classical | jazz | lofi | touhou |
|---|---|---|---|---|---|
| bpm_range | [84,132] | [60,168] | [110,208] | [66,92] | [150,192] |
| density_ref.__global__ | [6,30] | [2,16] | [6,32] | [5,26] | [10,48] |
| density_ref.melody | [4,12] | [2,8] | [4,14] | [3,10] | [6,20] |
| density_ref.harmony | [3,10] | [1,6] | [3,12] | [2,8] | [4,16] |
| density_ref.bass | [2,6] | [1,4] | [2,8] | [1,5] | [3,10] |
| swing_offsets | [] | [] | [200] | [180] | [] |
| drum_patterns.kick | [0,960] | — | [0,960] | [0,1020] | [0,840,960,1800] |
| drum_patterns.snare | [480,1440] | — | [480,1440] | [480,1560] | [480,1440] |
| drum_patterns.hat | [0,240,480,720,960,1200,1440,1680] | — | [240,720,1200,1680] | [120,600,1080,1560] | [0,240,480,720,960,1200,1440,1680] |

classical omits `drum_patterns` entirely (`{}`). Jazz hat = ride-ish sparse; document in its rhythm.md that 42 stands in for ride.

Per-style identity facts that MUST appear (tests grep keywords): pop — four-piece band idiom, I-V-vi-IV family; classical — functional harmony, no drum track, authentic/plagal cadences; jazz — ii-V-I, seventh chords as default quality, walking bass, swing feel; lofi — maj7/min7/9 colors, 66-92 BPM, lazy swung drums, sparse texture; touhou — fast tempo, trumpet lead program 56, driving piano arpeggios (program 0), high chorus energy.

- [ ] **Step 1: Write failing test**

`tests/test_style_packs.py`:
```python
import json

import pytest

from miidi.schema.chords import parse_chord
from miidi.skills.loader import available_styles, load_style_pack

EXPECTED = ["classical", "jazz", "lofi", "pop", "touhou"]


def test_all_styles_present():
    assert available_styles() == EXPECTED


@pytest.mark.parametrize("name", EXPECTED)
def test_pack_loads_and_structure(name):
    pack = load_style_pack(name)
    for attr in ("skill_md", "instruments_md", "harmony_md", "rhythm_md"):
        assert getattr(pack, attr).strip(), f"{name}.{attr} empty"
    skill = pack.skill_md
    assert "## Identity" in skill and "## Workflow" in skill and "## Output Rules" in skill
    assert "| role |" in pack.instruments_md and "GM program" in pack.instruments_md
    assert "# Harmony Vocabulary" in pack.harmony_md
    assert "## Cadences" in pack.harmony_md
    assert "## Drum Patterns" in pack.rhythm_md or name == "classical"
    assert "ppq=480" in skill or "480" in skill


@pytest.mark.parametrize("name", EXPECTED)
def test_every_chord_symbol_parses(name):
    import re
    pack = load_style_pack(name)
    body = pack.harmony_md.replace("##", " ").replace("#", " ")
    tokens = re.findall(r"\b([A-G][b#]?(?:maj7|m7b5|m7|min|m|dim7|dim|aug|sus4|sus2|add9|6|m6|7|5)?)\b",
                        body)
    checked = 0
    for t in tokens:
        if len(t) == 1 and t in "ABDEFG":
            continue
        parse_chord(t)
        checked += 1
    assert checked >= 6, f"{name}: too few chord symbols enumerated"


def test_defaults_match_contract():
    contract = {
        "pop": {"bpm": (84, 132), "swing": []},
        "classical": {"bpm": (60, 168), "swing": []},
        "jazz": {"bpm": (110, 208), "swing": [200]},
        "lofi": {"bpm": (66, 92), "swing": [180]},
        "touhou": {"bpm": (150, 192), "swing": []},
    }
    for name, want in contract.items():
        d = load_style_pack(name).defaults
        assert tuple(d.bpm_range) == want["bpm"], name
        assert list(d.swing_offsets) == want["swing"], name
        assert "__global__" in d.density_ref, name
    assert load_style_pack("classical").defaults.drum_patterns == {}
    for n in ("pop", "jazz", "lofi", "touhou"):
        dp = load_style_pack(n).defaults.drum_patterns
        assert set(dp) >= {"kick", "snare", "hat"}, n
    assert load_style_pack("jazz").defaults.swing_offsets == [200]


@pytest.mark.parametrize("name,kw", [
    ("pop", ["I-V-vi-IV"]),
    ("classical", ["cadence"]),
    ("jazz", ["ii-V-I"]),
    ("lofi", ["maj7"]),
    ("touhou", ["trumpet"]),
])
def test_identity_keywords(name, kw):
    text = load_style_pack(name)
    blob = (text.skill_md + text.harmony_md + text.instruments_md).lower()
    for k in kw:
        assert k.lower() in blob, f"{name} missing keyword {k}"
```

- [ ] **Step 2: Verify failure** — Run: `python -m pytest tests/test_style_packs.py -v`, expect FAIL (styles absent).

- [ ] **Step 3: Author the packs** — Write all 25 files meeting the Content Contract. `SKILL.md` for pop follows this exact skeleton (others mirror it with their facts):

```markdown
# Pop Style

## Identity
Bright four-piece band idiom: drums, electric bass, piano or guitar comping, and a
single memorable lead. Diatonic major/minor vocabulary built around the I-V-vi-IV
family, clear phrase structure, and steady backbeat energy.

## Workflow
- Planning stage reads: harmony.md (progressions), instruments.md (palette).
- Composition stage reads: rhythm.md (patterns), instruments.md (registers).
- Never read files not listed for your stage.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
```

Author the remaining 24 files against the contract table above. Chord symbols in harmony.md must ALL parse (no `Cmaj9`, no `Am/C`). Classical lists NO drum patterns and says so explicitly.

- [ ] **Step 4: Verify pass + suite** — `python -m pytest tests/test_style_packs.py tests/ -q` → green.
- [ ] **Step 5: Commit**

```bash
git add skills tests/test_style_packs.py
git commit -m "feat: five style packs with evaluator-aligned defaults"
```

---
### Task 4: Prompt templates

**Files:**
- Create: `src/miidi/pipeline/__init__.py`, `src/miidi/pipeline/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces (all pure string builders; no client calls):
  - `plan_system(pack: StylePack) -> str` — role definition, JSON-only contract, the brief schema (below), style identity excerpt
  - `plan_user(user_prompt: str, pack: StylePack) -> str` — user request + bpm range + harmony vocabulary excerpt from `pack.harmony_md`
  - `compose_system(track_spec: dict, pack: StylePack) -> str` — single-track composer role with tick-grid rules and the track's role guidance from `pack.rhythm_md`/`instruments_md`
  - `compose_user(brief_json: str, track_spec: dict, context_block: str) -> str` — full plan JSON + this track's spec + prior-track context block; demands `{"notes": [[onset,dur,pitch,velocity], ...]}` only
  - `review_system() -> str`, `review_user(report_text: str, track_options: list[str], brief_json: str) -> str` — returns `{"track": "<name>", "notes": [...]}` patch or `{"track": null}`
  - Every template ends instructing: output ONLY a JSON object, no markdown fences, no commentary.

Brief JSON schema (embedded verbatim in `plan_system`):
```json
{
  "title": "string",
  "bpm": integer,
  "time_signature": [num, den],
  "tonic_pc": 0-11,
  "mode": "major" | "minor",
  "structure": [{"name": "...", "start_bar": 0, "bars": N}],
  "harmony": [{"bar": 0, "dur_bars": 1.0, "symbol": "C"}],
  "instruments": [{"name": "...", "program": 0-127, "role": "melody|harmony|bass|counter|color|drums",
                   "description": "one line of musical intent"}]
}
```

- [ ] **Step 1: Write failing test**

`tests/test_prompts.py`:
```python
from pathlib import Path

import pytest

from miidi.eval.style import StyleDefaults
from miidi.pipeline.prompts import (
    compose_system, compose_user, plan_system, plan_user,
    review_system, review_user,
)

PACK = StylePack = None


@pytest.fixture()
def pack():
    from miidi.skills.loader import load_style_pack
    return load_style_pack("pop")


def test_plan_system_contains_schema_and_contract(pack):
    text = plan_system(pack)
    assert '"instruments"' in text and '"symbol"' in text
    assert "JSON" in text and "no markdown" in text.lower()
    assert "Pop" in text or "pop" in text


def test_plan_user_embeds_range_and_vocab(pack):
    text = plan_user("一首关于夏天的歌", pack)
    assert "一首关于夏天的歌" in text
    assert "84" in text and "132" in text
    assert len(text) > 200


def test_compose_prompts_carry_grid_rules(pack):
    spec = {"name": "Lead", "program": 73, "role": "melody",
            "description": "singing quarter-note melody"}
    sys_text = compose_system(spec, pack)
    usr_text = compose_user('{"bpm": 100}', spec, "MELODY NOTES: [[0,480,72,96]]")
    assert "ppq=480" in sys_text or "480" in sys_text
    assert '"notes"' in usr_text
    assert "[[0,480,72,96]]" in usr_text


def test_review_prompt_lists_tracks():
    sys_text = review_system()
    usr = review_user("bar5 bass not chord tone", ["Bs", "Pad"], '{"bpm": 100}')
    assert '"track"' in usr and "Bs" in usr
    assert "JSON" in sys_text
```

- [ ] **Step 2: Verify failure** — ImportError expected.

- [ ] **Step 3: Implement**

`src/miidi/pipeline/__init__.py`: empty.

`src/miidi/pipeline/prompts.py`:
```python
from __future__ import annotations

from miidi.skills.loader import StylePack

_JSON_ONLY = ("Output ONLY a single JSON object matching the schema. "
              "No markdown fences, no commentary, no trailing text.")

_BRIEF_SCHEMA = """{
  "title": "string",
  "bpm": integer,
  "time_signature": [numerator, denominator],
  "tonic_pc": 0-11,
  "mode": "major" or "minor",
  "structure": [{"name": "intro|verse|chorus|bridge|outro|...", "start_bar": 0, "bars": 4}],
  "harmony": [{"bar": 0, "dur_bars": 1.0, "symbol": "C"}],
  "instruments": [{"name": "Lead", "program": 73,
                   "role": "melody|harmony|bass|counter|color|drums",
                   "description": "one line of musical intent"}]
}"""

_GRID_RULES = (
    "Time is integer ticks on the ppq=480 grid (quarter=480, eighth=240, sixteenth=120, "
    "eighth-triplet=160). Notes are [onset_tick, duration_tick, midi_pitch, velocity]. "
    "Rests are gaps between notes. Chords inside one track are several entries sharing "
    "the same onset. Velocity is 1-127 and must vary musically."
)


def _style_identity(pack: StylePack) -> str:
    lines = pack.skill_md.splitlines()
    keep = []
    grab = False
    for line in lines:
        if line.startswith("## Identity"):
            grab = True
            continue
        if grab and line.startswith("## "):
            break
        if grab:
            keep.append(line)
    return "\n".join(keep).strip()


def plan_system(pack: StylePack) -> str:
    return (
        "You are an expert music planner. Given a natural-language request you design "
        "a piece: tempo, key, section structure, chord timeline, and instrument roster.\n\n"
        f"STYLE — {pack.name.upper()}\n{_style_identity(pack)}\n\n"
        f"BRIEF SCHEMA\n{_BRIEF_SCHEMA}\n\n"
        "Rules:\n"
        "- structure sections must tile the song contiguously starting at bar 0 (start_bar of "
        "each equals previous start_bar + bars).\n"
        "- harmony symbols must be plain chord symbols (C, Am, Fmaj7, Bm7b5...). No slash "
        "chords, no 9/11/13 extensions.\n"
        "- instruments: 3 to 6 entries covering at least one 'melody', one 'bass', one "
        "'harmony'; drums entry uses role 'drums'.\n"
        f"- bpm inside the style's typical range given in the request.\n"
        f"{_JSON_ONLY}"
    )


def plan_user(user_prompt: str, pack: StylePack) -> str:
    d = pack.defaults
    lo, hi = int(d.bpm_range[0]), int(d.bpm_range[1])
    vocab = pack.harmony_md[:1600]
    return (
        f"REQUEST:\n{user_prompt}\n\n"
        f"Typical BPM range for {pack.name}: {lo}-{hi}. Choose within it.\n\n"
        f"HARMONY VOCABULARY (use these symbols):\n{vocab}\n\n{_JSON_ONLY}"
    )


def _role_guidance(track_spec: dict, pack: StylePack) -> str:
    role = track_spec.get("role", "harmony")
    if role == "drums":
        return pack.rhythm_md[:1400]
    if role == "melody":
        return f"{pack.instruments_md[:900]}\nWrite a singable, memorable line."
    if role == "bass":
        return f"{pack.instruments_md[:900]}\nSupport the harmony root motion."
    return f"{pack.harmony_md[:900]}\nRealize the declared chords for this register."


def compose_system(track_spec: dict, pack: StylePack) -> str:
    name = track_spec.get("name", "track")
    program = track_spec.get("program", 0)
    role = track_spec.get("role", "harmony")
    desc = track_spec.get("description", "")
    return (
        f"You are a professional arranger writing ONE track: '{name}' "
        f"(GM program {program}, role '{role}'). Intent: {desc}\n\n"
        f"GRID RULES\n{_GRID_RULES}\n\n"
        f"STYLE GUIDANCE\n{_role_guidance(track_spec, pack)}\n\n"
        'Respond ONLY: {"notes": [[onset,dur,pitch,velocity], ...]}'
    )


def compose_user(brief_json: str, track_spec: dict, context_block: str) -> str:
    return (
        f"MUSICAL PLAN\n{brief_json}\n\n"
        f"YOUR TRACK\n{track_spec['name']} (role {track_spec.get('role')})\n\n"
        f"CONTEXT FROM OTHER TRACKS\n{context_block or '(you start first — nothing yet)'}\n\n"
        "Write the whole track over the full structure length.\n"
        'Output ONLY {"notes": [[onset,dur,pitch,velocity], ...]}'
    )


def review_system() -> str:
    return (
        "You are a meticulous composition fixer. You receive an evaluation report "
        "listing concrete violations and the current plan. Choose ONE track worth "
        "rewriting to fix the worst issues, and output its complete replacement notes.\n"
        f"GRID RULES\n{_GRID_RULES}\n\n"
        'Respond ONLY either {"track": "<name>", "notes": [[onset,dur,pitch,velocity], ...]} '
        'or {"track": null} when nothing is worth changing.'
    )


def review_user(report_text: str, track_options: list[str],
                brief_json: str) -> str:
    opts = ", ".join(track_options)
    return (
        f"EVALUATION REPORT\n{report_text}\n\n"
        f"CANDIDATE TRACKS: {opts}\n\nMUSICAL PLAN\n{brief_json}\n\n"
        'Fix the highest-impact violations. Output ONLY the JSON decision.'
    )
```

Note: `_style_identity` slices between `## Identity` and the next heading — packs authored in Task 3 guarantee that heading exists (`test_pack_loads_and_structure` asserts `## Identity`).

- [ ] **Step 4: Verify pass + suite**
- [ ] **Step 5: Commit**

```bash
git add src/miidi/pipeline tests/test_prompts.py
git commit -m "feat: stage prompt templates with embedded grid rules"
```

---

### Task 5: Pipeline stages (plan / compose / self-review)

**Files:**
- Create: `src/miidi/pipeline/brief.py`, `src/miidi/pipeline/stages.py`
- Test: `tests/test_stages.py`

**Interfaces:**
- Consumes: kernel APIs + prompts module + LLMClient protocol (anything with `.respond_json(system, user, temperature=0.0)`).
- Produces:
  - `StageError(RuntimeError)`
  - `MusicBrief` pydantic model: `title/bpm/time_signature/key(KeySig)/structure[Section]/harmony[ChordSpan]/instruments[list[InstrumentSpec]]`; `InstrumentSpec(name, program: 0-127, role: TrackRole, description: str)`; `.to_skeleton() -> Composition` (meta+structure+harmony+empty tracks in instrument order; drums get `is_drum=True`)
  - `make_brief(client, pack, user_prompt) -> MusicBrief` — one LLM call; validation ladder: JSON parse (client raises), pydantic validate, chord symbols parseable via `parse_chord` (unparseable ⇒ ONE retry appending the error list, then `StageError`), sections contiguity auto-repair (recompute start_bar cumulatively, record note), bpm clamped into pack range (record note)
  - `compose_track(client, pack, brief, spec, context_block) -> tuple[Track, list[str]]` — one call + normalize via `normalize_raw({"meta": ..., "tracks": [{spec, "notes": ...}]})`; errors ⇒ up to 2 retries feeding back error strings; still bad ⇒ `StageError`; returns repairs log
  - `build_context(kind: str, tracks: dict[str, Track]) -> str` — `"full"` serializes notes lists; `"pc_summary"` renders per-bar pitch-class histograms (≤8 bars shown per line); drums never included
  - `self_review(client, comp, defaults, max_rounds=2) -> tuple[Composition, list[dict]]` — loop: `evaluate_rules` → format report text (violations top-12 lines + per-axis scores) → `respond_json(review_*)` → patch replaces named track (validate; invalid patch rejected with logged reason, loop breaks) → stop when R_rule improvement < 1.0 or rounds exhausted; returns final comp + trajectory `[{"round": 0, "R_rule": ...}, ...]`

Context policy (spec §5.1 ②): melody runs first with empty context; bass/harmony get `"full"` melody serialization; counter/color get `"pc_summary"` of all prior non-drum tracks; drums run on rhythm.md guidance alone (empty context).

- [ ] **Step 1: Write failing tests**

`tests/test_stages.py`:
```python
import pytest
from pydantic import ValidationError

from miidi.eval.style import StyleDefaults
from miidi.llm.client import LLMError
from miidi.pipeline.brief import InstrumentSpec, MusicBrief
from miidi.pipeline.stages import (
    StageError, build_context, compose_track, make_brief, self_review,
)
from miidi.schema.model import Composition, Track


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def respond_json(self, system, user, temperature=0.0):
        self.calls.append((system, user))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


BRIEF_OK = {
    "title": "Summer", "bpm": 100, "time_signature": [4, 4],
    "tonic_pc": 0, "mode": "major",
    "structure": [
        {"name": "verse", "start_bar": 0, "bars": 4},
        {"name": "chorus", "start_bar": 4, "bars": 4},
    ],
    "harmony": [
        {"bar": 0, "dur_bars": 4.0, "symbol": "C"},
        {"bar": 4, "dur_bars": 4.0, "symbol": "G"},
    ],
    "instruments": [
        {"name": "Lead", "program": 73, "role": "melody", "description": "tune"},
        {"name": "Bs", "program": 33, "role": "bass", "description": "roots"},
    ],
}


def pack_pop():
    from miidi.skills.loader import load_style_pack
    return load_style_pack("pop")


def test_make_brief_happy_path():
    client = FakeClient([BRIEF_OK])
    brief = make_brief(client, pack_pop(), "summer song")
    assert brief.title == "Summer"
    comp = brief.to_skeleton()
    assert comp.tracks[0].is_drum is False
    assert comp.total_bars() == 8.0


def test_make_brief_repairs_unparseable_chord_then_fails():
    bad = {**BRIEF_OK, "harmony": [{"bar": 0, "dur_bars": 4.0, "symbol": "Cmaj9"}]}
    client = FakeClient([bad, bad])
    with pytest.raises(StageError):
        make_brief(client, pack_pop(), "x")
    assert len(client.calls) == 2


def test_make_brief_second_try_recovers():
    bad = {**BRIEF_OK, "harmony": [{"bar": 0, "dur_bars": 4.0, "symbol": "Q7"}]}
    client = FakeClient([bad, BRIEF_OK])
    assert make_brief(client, pack_pop(), "x").title == "Summer"


def test_make_brief_clamps_bpm_into_style_range():
    hot = {**BRIEF_OK, "bpm": 300}
    client = FakeClient([hot])
    brief = make_brief(client, pack_pop(), "x")
    assert pack_pop().defaults.bpm_range[0] <= brief.bpm <= pack_pop().defaults.bpm_range[1]


def test_make_brief_contiguity_repair():
    gapped = {**BRIEF_OK,
              "structure": [{"name": "a", "start_bar": 0, "bars": 2},
                            {"name": "b", "start_bar": 9, "bars": 2}]}
    client = FakeClient([gapped])
    brief = make_brief(client, pack_pop(), "x")
    assert brief.structure[1].start_bar == 2


NOTES_OK = {"notes": [[0, 480, 60, 96], [480, 480, 62, 96]]}


def test_compose_track_success():
    client = FakeClient([NOTES_OK])
    spec = {"name": "Lead", "program": 73, "role": "melody", "description": ""}
    track, repairs = compose_track(client, pack_pop(),
                                  MusicBrief.model_validate(
                                      {**BRIEF_OK}), spec, "")
    assert isinstance(track, Track)
    assert track.notes[0] == (0, 480, 60, 96)


def test_compose_track_retry_then_stage_error():
    client = FakeClient([{"notes": [[0, 480, 999, 96]]},
                         {"notes": [[0, 480, 999, 96]]},
                         {"notes": [[0, 480, 999, 96]]}])
    spec = {"name": "L", "program": 73, "role": "melody", "description": ""}
    with pytest.raises(StageError):
        compose_track(client, pack_pop(), MusicBrief.model_validate({**BRIEF_OK}),
                      spec, "")


def test_build_context_kinds():
    tracks = {"Mel": Track(name="Mel", role="melody",
                           notes=[(0, 480, 60, 96), (480, 480, 64, 96)])}
    full = build_context("full", tracks)
    assert "[[0, 480, 60, 96]" in full.replace("(", "[").replace(")", "]") or "60" in full
    summary = build_context("pc_summary", tracks)
    assert "bar" in summary.lower()


def test_self_review_stops_on_null_patch():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96), (480, 480, 64, 96),
                                            (960, 480, 67, 96), (1440, 480, 72, 96)])])
    client = FakeClient([{"track": None}])
    out, traj = self_review(client, comp, StyleDefaults(), max_rounds=2)
    assert traj[0]["round"] == 0
    assert out.tracks[0].notes == comp.tracks[0].notes


def test_self_review_applies_valid_patch():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96), (480, 480, 64, 96),
                                            (960, 480, 67, 96), (1440, 480, 72, 96)])])
    patched = {"track": "L",
               "notes": [[0, 480, 60, 80], [480, 480, 64, 90],
                         [960, 480, 67, 100], [1440, 480, 72, 110]]}
    client = FakeClient([patched, {"track": None}])
    out, traj = self_review(client, comp, StyleDefaults())
    assert out.tracks[0].notes[-1][3] == 110
    assert len(traj) >= 2


def test_self_review_rejects_invalid_patch_and_breaks():
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96)])])
    client = FakeClient([{"track": "L", "notes": [[0, 480, 200, 96]]}])
    out, _traj = self_review(client, comp, StyleDefaults())
    assert out.tracks[0].notes == comp.tracks[0].notes
```

- [ ] **Step 2: Verify failure** — ImportError expected.

- [ ] **Step 3: Implement**

`src/miidi/pipeline/brief.py`:
```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from miidi.schema.chords import ChordParseError, parse_chord
from miidi.schema.model import ChordSpan, Composition, KeySig, Meta, Section, TrackRole


class InstrumentSpec(BaseModel):
    name: str
    program: int = Field(ge=0, le=127)
    role: TrackRole
    description: str = ""


class MusicBrief(BaseModel):
    title: str = "untitled"
    bpm: int = Field(default=120, ge=20, le=300)
    time_signature: tuple[int, int] = (4, 4)
    tonic_pc: int = Field(default=0, ge=0, le=11)
    mode: Literal["major", "minor"] = "major"
    structure: list[Section]
    harmony: list[ChordSpan]
    instruments: list[InstrumentSpec]

    def to_skeleton(self) -> Composition:
        meta = Meta(title=self.title, bpm=self.bpm,
                    time_signature=self.time_signature,
                    key=KeySig(tonic_pc=self.tonic_pc, mode=self.mode))
        tracks = []
        for inst in self.instruments:
            tracks.append(Track(name=inst.name, program=inst.program,
                                role=inst.role, is_drum=(inst.role == "drums")))
        return Composition(meta=meta, structure=self.structure,
                           harmony=self.harmony, tracks=tracks)

    def brief_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def validate_symbols(cls, spans: list[ChordSpan]) -> list[str]:
        errors = []
        for h in spans:
            try:
                parse_chord(h.symbol)
            except ChordParseError as exc:
                errors.append(f"chord {h.symbol!r}: {exc}")
        return errors
```

`src/miidi/pipeline/stages.py`:
```python
from __future__ import annotations

import json

from miidi.eval.score import evaluate_rules
from miidi.eval.style import StyleDefaults
from miidi.llm.client import LLMClient
from miidi.pipeline.brief import MusicBrief
from miidi.pipeline.prompts import (
    compose_system, compose_user, plan_system, plan_user, review_system,
    review_user,
)
from miidi.schema.model import Composition, Section, Track
from miidi.schema.normalize import normalize_raw
from miidi.schema.validate import validate_composition
from miidi.skills.loader import StylePack


class StageError(RuntimeError):
    pass


def _to_music_brief(raw: dict, pack: StylePack) -> tuple[MusicBrief, list[str]]:
    notes: list[str] = []
    cursor = 0
    fixed_sections = []
    for s in raw.get("structure", []):
        start = s.get("start_bar")
        if not isinstance(start, int) or start < cursor:
            start = cursor
            notes.append(f"section {s.get('name')!r}: start_bar repaired to {cursor}")
        fixed = dict(s)
        fixed["start_bar"] = start
        fixed_sections.append(fixed)
        cursor = start + int(s.get("bars", 0))
    raw["structure"] = fixed_sections
    lo, hi = pack.defaults.bpm_range
    bpm = raw.get("bpm")
    if isinstance(bpm, int) and not lo <= bpm <= hi:
        clamped = max(int(lo), min(int(hi), bpm))
        notes.append(f"bpm {bpm} outside style range; clamped to {clamped}")
        raw["bpm"] = clamped
    brief = MusicBrief.model_validate(raw)
    errors = MusicBrief.validate_symbols(brief.harmony)
    return brief, errors + notes


def make_brief(client: LLMClient, pack: StylePack, user_prompt: str) -> MusicBrief:
    last_notes: list[str] = []
    for attempt in range(2):
        system = plan_system(pack)
        user = plan_user(user_prompt, pack)
        if last_notes:
            user += ("\nPREVIOUS ATTEMPT REJECTED:\n" + "\n".join(last_notes)
                     + "\nFix these and return the full corrected JSON.")
        raw = client.respond_json(system, user)
        try:
            brief, notes = _to_music_brief(raw, pack)
        except Exception as exc:
            last_notes = [f"schema/validation error: {exc}"]
            continue
        hard_errors = [n for n in notes if n.startswith("chord")]
        if hard_errors:
            last_notes = hard_errors
            continue
        return brief
    raise StageError(f"planner failed after retry: {last_notes}")


def build_context(kind: str, tracks: dict[str, Track]) -> str:
    blocks = []
    for name, t in tracks.items():
        if t.is_drum:
            continue
        if kind == "full":
            rows = [[o, d, p, v] for o, d, p, v in t.notes]
            blocks.append(f"{name} ({t.role}) notes: {rows}")
        else:
            bar = 1920
            hist: dict[int, set[int]] = {}
            for o, d, p, _v in t.notes:
                hist.setdefault(o // bar, set()).add(p % 12)
            pretty = ", ".join(f"bar{b}:{sorted(pcs)}" for b, pcs in sorted(hist.items())[:16])
            blocks.append(f"{name} ({t.role}) per-bar pitch classes: {pretty}")
    return "\n".join(blocks)


def compose_track(client: LLMClient, pack: StylePack, brief: MusicBrief,
                  spec, context_block: str) -> tuple[Track, list[str]]:
    spec_dict = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)
    feedback: list[str] = []
    for attempt in range(3):
        raw = client.respond_json(
            compose_system(spec_dict, pack),
            compose_user(brief.brief_json(), spec_dict, context_block))
        merged = {**spec_dict, "notes": raw.get("notes", [])}
        result = normalize_raw({
            "meta": json.loads(brief.brief_json()),
            "tracks": [merged],
        })
        if result.composition is None or not result.composition.tracks:
            feedback = result.errors[:10] or ["unparseable notes"]
            continue
        skeleton = result.composition
        viols = validate_composition(skeleton)
        if viols:
            feedback = [f"{v.location}: {v.message}" for v in viols][:10]
            continue
        return skeleton.tracks[0], result.repairs
    raise StageError(f"track {spec_dict.get('name')!r} failed: {feedback}")
```

Continue `stages.py`:
```python
def _report_text(comp: Composition, defaults: StyleDefaults) -> str:
    report = evaluate_rules(comp, defaults)
    if report.invalid:
        return "INVALID COMPOSITION:\n" + "\n".join(
            f"{v.location}: {v.message}" for v in report.violations[:12])
    axis_lines = [f"{k}={v.score:.2f}" for k, v in report.axes.items()]
    gate_lines = [f"G_{k}={v:.2f}" for k, v in report.gates.items()]
    viol_lines = [f"- {v.location}: {v.message}" for v in report.violations][:12]
    parts = [f"R_rule={report.R_rule:.1f}",
             "axes: " + ", ".join(axis_lines),
             "gates: " + ", ".join(gate_lines)]
    if viol_lines:
        parts.append("violations:")
        parts.extend(viol_lines)
    else:
        parts.append("violations: none listed")
    return "\n".join(parts)


def self_review(client: LLMClient, comp: Composition, defaults: StyleDefaults,
                max_rounds: int = 2) -> tuple[Composition, list[dict]]:
    current = comp
    trajectory: list[dict] = []
    prev_score = float("-inf")
    for round_index in range(max_rounds):
        report = evaluate_rules(current, defaults)
        trajectory.append({"round": round_index, "R_rule": round(report.R_rule, 2)})
        if report.R_rule - prev_score < 1.0 and round_index > 0:
            break
        prev_score = report.R_rule
        options = [t.name for t in current.tracks if not t.is_drum] or \
                  [t.name for t in current.tracks]
        reply = client.respond_json(
            review_system(),
            review_user(_report_text(current, defaults), options,
                        json.dumps(current.meta.model_dump())))
        track_name = reply.get("track")
        notes = reply.get("notes")
        if not track_name or not isinstance(notes, list):
            trajectory[-1]["action"] = "kept"
            break
        target = next((t for t in current.tracks if t.name == track_name), None)
        if target is None:
            trajectory[-1]["action"] = f"unknown track {track_name!r}; kept"
            break
        spec = {"name": target.name, "program": target.program,
                "role": target.role, "is_drum": target.is_drum}
        result = normalize_raw({
            "meta": current.meta.model_dump(),
            "tracks": [{**spec, "notes": notes}],
        })
        if (result.composition is None or not result.composition.tracks
                or validate_composition(result.composition)):
            trajectory[-1]["action"] = "patch rejected; kept"
            break
        patched_track = result.composition.tracks[0]
        new_tracks = [patched_track if t.name == track_name else t
                      for t in current.tracks]
        current = current.model_copy(update={"tracks": new_tracks})
        trajectory[-1]["action"] = f"patched {track_name}"
    return current, trajectory
```

- [ ] **Step 4: Verify pass + suite**
- [ ] **Step 5: Commit**

```bash
git add src/miidi/pipeline tests/test_stages.py
git commit -m "feat: plan/compose/self-review stages with repair ladders"
```

---
### Task 6: Orchestrator + session store

**Files:**
- Create: `src/miidi/session/__init__.py`, `src/miidi/session/store.py`, `src/miidi/pipeline/orchestrator.py`
- Test: `tests/test_session_store.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Produces:
  - `SessionStore(root: Path)`:
    - `create(prompt: str, style: str) -> str` — id = UTC timestamp `%Y%m%d-%H%M%S` + 4 hex chars from `uuid4().hex` (session identity only — no RNG on eval path); writes `<root>/<id>/meta.json` `{"id","prompt","style","created"}`
    - `save_version(sid, label, comp: Composition, extra: dict | None) -> int` — version numbers 1..n; file `<root>/<sid>/v{n}.json` = `{"version", "label", "composition": comp.model_dump(), "extra"}`; updates meta's version index
    - `list_versions(sid) -> list[dict]`, `load_version(sid, v) -> dict`, `latest(sid) -> int`
    - unknown sid → `FileNotFoundError`
  - `PipelineResult` dataclass: `comp: Composition | None, brief: MusicBrief | None, midi_path: Path | None, trajectory: list[dict], stage_log: list[str]`
  - `run_pipeline(user_prompt: str, style: str, client, out_dir: Path | None = None,
                 max_review_rounds: int = 2, store: SessionStore | None = None) -> PipelineResult`
    Sequence (spec §5.1): make_brief → skeleton → per-instrument compose in dependency order
    (`melody → bass → harmony → counter → color → drums`; stable within role by roster order)
    with context policy (melody first empty; bass/harmony get full melody; counter/color get pc_summary; drums last empty)
    → assemble Composition → self_review loop → generate_midi when out_dir given.
    Every stage appends to `stage_log`; LLM/Stage errors abort with partial result (comp=None if before assembly).
    When `store` given: save_version("plan+compose") after assembly and save_version("reviewed") after loop.
  - `revise(store, client, sid, feedback: str, out_dir=None) -> PipelineResult`
    loads latest version; one LLM call classifies target layer via new prompt pair in prompts.py:
    `classify_revision_system()` / `classify_revision_user(feedback, track_names)` returning
    `{"layer": "harmony|structure|track|regenerate", "track": name|null}`; then:
    - `"track"`: re-run compose_track for that spec with feedback appended to context block;
    - `"harmony"`: re-run make_brief with original prompt + feedback, keep existing tracks whose names still exist, re-compose missing ones;
    - `"regenerate"`: full run_pipeline on `original_prompt + "\nRevision request: " + feedback`;
    saves a new version labeled `"revised"`.

- [ ] **Step 1: Write failing tests**

`tests/test_session_store.py`:
```python
import pytest

from miidi.schema.model import Composition, Track
from miidi.session.store import SessionStore


def comp():
    return Composition(tracks=[Track(name="L", notes=[(0, 480, 60, 96)])])


def test_create_and_versions(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create("rainy lofi", "lofi")
    v1 = store.save_version(sid, "initial", comp(), {"R_rule": 55.0})
    v2 = store.save_version(sid, "reviewed", comp(), None)
    assert (v1, v2) == (1, 2)
    versions = store.list_versions(sid)
    assert [v["label"] for v in versions] == ["initial", "reviewed"]
    loaded = store.load_version(sid, 1)
    assert loaded["composition"]["tracks"][0]["name"] == "L"
    assert store.latest(sid) == 2


def test_unknown_session_raises(tmp_path):
    store = SessionStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.list_versions("nope")
```

`tests/test_orchestrator.py`:
```python
from pathlib import Path

import pytest

from miidi.llm.client import LLMError
from miidi.pipeline.orchestrator import PipelineResult, revise, run_pipeline


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def respond_json(self, system, user, temperature=0.0):
        self.calls.append((system, user))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


BRIEF = {
    "title": "T", "bpm": 100, "time_signature": [4, 4],
    "tonic_pc": 0, "mode": "major",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 2}],
    "harmony": [{"bar": 0, "dur_bars": 2.0, "symbol": "C"}],
    "instruments": [
        {"name": "Lead", "program": 73, "role": "melody", "description": "tune"},
        {"name": "Bs", "program": 33, "role": "bass", "description": "roots"},
    ],
}


def lead_ok(_sys, _usr):
    return {"notes": [[o * 240, 240, p, 90] for o, p in
                      enumerate([72, 74, 76, 72, 74, 76, 74, 72])]}   # spans 8 eighths=1920*... 8*240=1920 ticks = 1 bar


def bass_ok(_sys, _usr):
    return {"notes": [[0, 960, 36, 88], [960, 960, 43, 88]]}


def test_run_pipeline_end_to_end_with_fake_llm(tmp_path):
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         {"track": None}])
    result = run_pipeline("a tiny tune", "pop", client, out_dir=tmp_path)
    assert isinstance(result, PipelineResult)
    assert result.comp is not None and len(result.comp.tracks) == 2
    names = {t.name for t in result.comp.tracks}
    assert names == {"Lead", "Bs"}
    assert result.midi_path is not None and Path(result.midi_path).exists()
    assert any("brief" in s for s in result.stage_log)
    assert result.trajectory and result.trajectory[0]["round"] == 0


def test_run_pipeline_saves_versions_when_store_given(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "sessions")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         {"track": None}])
    sid_holder = {}
    result = run_pipeline("x", "pop", client, store=store)

    assert result.comp is not None
    sid = store.list_sessions()[0]
    assert store.latest(sid) >= 2


def test_planner_failure_returns_partial(tmp_path):
    client = FakeClient([LLMError("down")])
    result = run_pipeline("x", "pop", client)
    assert result.comp is None
    assert any("brief" in s.lower() or "fail" in s.lower() for s in result.stage_log)


def test_revise_regenerates_track(tmp_path):
    from miidi.session.store import SessionStore
    store = SessionStore(tmp_path / "s")
    client = FakeClient([BRIEF, lead_ok(None, None), bass_ok(None, None),
                         {"track": None}])
    run_pipeline("x", "pop", client, store=store)
    sid = store.list_sessions()[0]
    quieter = {"notes": [[0, 1920, 60, 40]]}
    client2 = FakeClient([{"layer": "track", "track": "Lead"},
                          quieter, {"track": None}])
    out = revise(store, client2, sid, "make lead quieter")
    lead = next(t for t in out.comp.tracks if t.name == "Lead")
    assert lead.notes[-1][3] == 40
```

- [ ] **Step 2: Verify failure** — ImportErrors expected.

- [ ] **Step 3: Implement**

Append to `src/miidi/pipeline/prompts.py`:
```python
def classify_revision_system() -> str:
    return (
        "You route a user's revision request for a generated song to the right layer.\n"
        'Respond ONLY JSON: {"layer": "track|harmony|structure|regenerate", '
        '"track": "<name>" or null}\n'
        "- 'track': feedback targets ONE instrument's performance (density, register, "
        "pattern, feel). Set track to that instrument's name.\n"
        "- 'harmony': feedback targets chord choices/progression.\n"
        "- 'structure': feedback targets form/section layout.\n"
        "- 'regenerate': anything else or ambiguous."
    )


def classify_revision_user(feedback: str, track_names: list[str]) -> str:
    return f"TRACKS: {', '.join(track_names)}\nFEEDBACK: {feedback}"
```

`src/miidi/session/__init__.py`: empty.

`src/miidi/session/store.py`:
```python
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from miidi.schema.model import Composition


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, sid: str) -> Path:
        d = self.root / sid
        if not d.is_dir():
            raise FileNotFoundError(f"unknown session {sid!r}")
        return d

    def create(self, prompt: str, style: str) -> str:
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        d = self.root / sid
        d.mkdir()
        meta = {"id": sid, "prompt": prompt, "style": style,
                "created": time.time(), "versions": []}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        return sid

    def save_version(self, sid: str, label: str, comp: Composition,
                     extra: dict | None) -> int:
        d = self._dir(sid)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        version = len(meta["versions"]) + 1
        payload = {"version": version, "label": label,
                   "composition": comp.model_dump(),
                   "extra": extra or {}}
        (d / f"v{version}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        meta["versions"].append({"version": version, "label": label})
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        return version

    def list_versions(self, sid: str) -> list[dict]:
        meta = json.loads(self._dir(sid).joinpath("meta.json").read_text(encoding="utf-8"))
        return meta["versions"]

    def load_version(self, sid: str, version: int) -> dict:
        return json.loads((self._dir(sid) / f"v{version}.json").read_text(encoding="utf-8"))

    def latest(self, sid: str) -> int:
        return max(v["version"] for v in self.list_versions(sid))

    def list_sessions(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def load_composition(self, sid: str, version: int) -> Composition:
        raw = self.load_version(sid, version)["composition"]
        return Composition.model_validate(raw)

    def session_meta(self, sid: str) -> dict:
        return json.loads(self._dir(sid).joinpath("meta.json").read_text(encoding="utf-8"))
```

`src/miidi/pipeline/orchestrator.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from miidi.pipeline.brief import InstrumentSpec, MusicBrief
from miidi.pipeline.prompts import (
    classify_revision_system, classify_revision_user, compose_system,
    compose_user,
)
from miidi.pipeline.stages import (
    StageError, build_context, compose_track, make_brief, self_review,
)
from miidi.render.midi import generate_midi
from miidi.schema.model import Composition
from miidi.session.store import SessionStore
from miidi.skills.loader import StylePack, load_style_pack

_ROLE_ORDER = ["melody", "bass", "harmony", "counter", "color", "drums"]


@dataclass
class PipelineResult:
    comp: Composition | None
    brief: MusicBrief | None
    midi_path: Path | None
    trajectory: list[dict] = field(default_factory=list)
    stage_log: list[str] = field(default_factory=list)


def _context_for(role: str, prior: dict) -> str:
    if not prior:
        return ""
    if role in ("bass", "harmony"):
        mel = {n: t for n, t in prior.items() if t.role == "melody"}
        if mel:
            return build_context("full", mel)
        return build_context("full", prior)
    if role in ("counter", "color"):
        return build_context("pc_summary", prior)
    return ""


def run_pipeline(user_prompt: str, style: str, client,
                 out_dir: Path | None = None, max_review_rounds: int = 2,
                 store: SessionStore | None = None) -> PipelineResult:
    log: list[str] = []
    pack: StylePack = load_style_pack(style)
    try:
        brief = make_brief(client, pack, user_prompt)
    except Exception as exc:
        log.append(f"brief failed: {exc}")
        return PipelineResult(comp=None, brief=None, midi_path=None, stage_log=log)
    log.append("brief ok")
    comp = brief.to_skeleton()

    specs = {s.name: s for s in brief.instruments}
    ordered = sorted(brief.instruments,
                     key=lambda s: (_ROLE_ORDER.index(s.role)
                                    if s.role in _ROLE_ORDER else 3))
    prior: dict[str, object] = {}
    for spec in ordered:
        ctx = _context_for(spec.role, prior)
        try:
            track, repairs = compose_track(client, pack, brief, spec, ctx)
        except Exception as exc:
            log.append(f"compose {spec.name} failed: {exc}")
            return PipelineResult(comp=None, brief=brief, midi_path=None,
                                  stage_log=log)
        prior[track.name] = track
        comp = comp.model_copy(update={
            "tracks": [track if t.name == track.name else t for t in comp.tracks]})
        log.append(f"composed {track.name}" + (f" ({len(repairs)} repairs)" if repairs else ""))
    assembled = comp
    if store is not None:
        sid = store.create(user_prompt, style)
        store.save_version(sid, "assembled", assembled, None)
        log.append(f"session {sid}: saved assembled")

    reviewed, trajectory = self_review(client, assembled, pack.defaults,
                                       max_rounds=max_review_rounds)
    log.append(f"self-review done ({len(trajectory)} rounds)")
    if store is not None:
        sid = store.list_sessions()[-1]
        store.save_version(sid, "reviewed", reviewed,
                           {"trajectory": trajectory})
        log.append("saved reviewed version")

    midi_path = None
    if out_dir is not None:
        midi_path = generate_midi(reviewed, Path(out_dir))
        log.append(f"midi written: {midi_path}")
    return PipelineResult(comp=reviewed, brief=brief, midi_path=midi_path,
                          trajectory=trajectory, stage_log=log)


def revise(store: SessionStore, client, sid: str, feedback: str,
           out_dir: Path | None = None) -> PipelineResult:
    meta = store.session_meta(sid)
    latest = store.load_composition(sid, store.latest(sid))
    pack = load_style_pack(meta["style"])
    track_names = [t.name for t in latest.tracks]
    routing = client.respond_json(classify_revision_system(),
                                  classify_revision_user(feedback, track_names))
    layer = routing.get("layer", "regenerate")
    target = routing.get("track")

    if layer == "track" and target in track_names:
        spec = next(s for s in _specs_from(latest) if s.name == target)
        context = f"{build_context('pc_summary', {t.name: t for t in latest.tracks})}\nUSER FEEDBACK: {feedback}"
        track, _repairs = compose_track(client, pack, _brief_from_comp(latest), spec, context)
        updated = latest.model_copy(update={
            "tracks": [track if t.name == target else t for t in latest.tracks]})
        version = store.save_version(sid, "revised", updated, {"feedback": feedback})
        midi_path = generate_midi(updated, out_dir) if out_dir else None
        return PipelineResult(comp=updated, brief=_brief_from_comp(latest),
                              midi_path=midi_path,
                              stage_log=[f"revised track {target} as v{version}"])

    merged_prompt = meta["prompt"] + "\nRevision request: " + feedback
    return run_pipeline(merged_prompt, meta["style"], client,
                        out_dir=out_dir, store=store)


def _specs_from(comp: Composition) -> list[InstrumentSpec]:
    role_hints = {"melody": "carry the tune", "bass": "support roots",
                  "drums": "groove"}
    return [InstrumentSpec(name=t.name, program=t.program, role=t.role,
                           description=role_hints.get(t.role, ""))
            for t in comp.tracks]


def _brief_from_comp(comp: Composition) -> MusicBrief:
    return MusicBrief(
        title=comp.meta.title, bpm=comp.meta.bpm,
        time_signature=comp.meta.time_signature,
        tonic_pc=comp.meta.key.tonic_pc, mode=comp.meta.key.mode,
        structure=comp.structure, harmony=comp.harmony,
        instruments=[InstrumentSpec(name=t.name, program=t.program,
                                    role=t.role, description="")
                     for t in comp.tracks],
    )
```

- [ ] **Step 4: Verify pass + suite**
- [ ] **Step 5: Commit**

```bash
git add src/miidi/session src/miidi/pipeline/orchestrator.py src/miidi/pipeline/prompts.py tests/test_session_store.py tests/test_orchestrator.py
git commit -m "feat: pipeline orchestrator with session persistence and revision routing"
```

---

### Task 7: CLI entry point

**Files:**
- Create: `src/miidi/cli.py`, `src/miidi/__main__.py`
- Modify: `pyproject.toml` (`[project.scripts] miidi = "miidi.cli:main"`), `README.md` (usage section)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `main(argv: list[str] | None = None) -> int` argparse CLI:
    - `miidi generate --style pop --prompt "..." [--out DIR] [--rounds N] [--no-review]` — runs pipeline with real client from env; prints stage log + final R_rule; exit 0 on success, 1 on failure with message on stderr
    - `miidi styles` — lists available styles
    - `miidi evaluate --json PATH` — loads composition JSON file, runs rules evaluator, prints report JSON
  - `python -m miidi` delegates to `main`.
- Real-network paths are NOT unit-tested (manual smoke only, documented).

- [ ] **Step 1: Write failing test**

`tests/test_cli.py`:
```python
import json

import pytest

from miidi.cli import main


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)

    def respond_json(self, system, user, temperature=0.0):
        return self.replies.pop(0)


BRIEF = {
    "title": "CLI", "bpm": 100, "time_signature": [4, 4],
    "tonic_pc": 0, "mode": "major",
    "structure": [{"name": "verse", "start_bar": 0, "bars": 2}],
    "harmony": [{"bar": 0, "dur_bars": 2.0, "symbol": "C"}],
    "instruments": [{"name": "L", "program": 73, "role": "melody",
                     "description": ""}],
}


def test_generate_with_fake_client(monkeypatch, tmp_path, capsys):
    from miidi import cli
    fake = FakeClient([BRIEF,
                       {"notes": [[0, 480, 72, 90], [480, 480, 74, 92],
                                  [960, 480, 76, 94], [1440, 480, 72, 90]]},
                       {"track": None}])
    monkeypatch.setattr(cli, "_make_default_client", lambda: fake)
    code = main(["generate", "--style", "pop",
                 "--prompt", "tiny", "--out", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "R_rule" in out


def test_styles_command(capsys):
    assert main(["styles"]) == 0
    assert "pop" in capsys.readouterr().out


def test_evaluate_command(tmp_path, capsys):
    from miidi.schema.model import Composition, Track
    comp = Composition(tracks=[Track(name="L", role="melody",
                                     notes=[(0, 480, 60, 96)])])
    p = tmp_path / "c.json"
    p.write_text(comp.model_dump_json())
    assert main(["evaluate", "--json", str(p)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "R_rule" in payload


def test_generate_failure_exit_code(monkeypatch):
    from miidi import cli
    def boom():
        raise RuntimeError("env broken")
    monkeypatch.setattr(cli, "_make_default_client", boom)
    assert main(["generate", "--style", "pop", "--prompt", "x"]) == 1
```

- [ ] **Step 2: Verify failure** — ImportError expected.

- [ ] **Step 3: Implement**

`src/miidi/cli.py`:
```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError


def _make_default_client():
    from miidi.llm.client import LLMClient, load_config
    return LLMClient(load_config())


def cmd_generate(args) -> int:
    from miidi.pipeline.orchestrator import run_pipeline
    try:
        client = _make_default_client()
    except Exception as exc:
        print(f"client init failed: {exc}", file=sys.stderr)
        return 1
    result = run_pipeline(args.prompt, args.style, client,
                          out_dir=Path(args.out) if args.out else None,
                          max_review_rounds=0 if args.no_review else args.rounds)
    for line in result.stage_log:
        print(line)
    if result.comp is None:
        return 1
    from miidi.eval.score import evaluate_rules
    from miidi.skills.loader import load_style_pack
    report = evaluate_rules(result.comp, load_style_pack(args.style).defaults)
    print(f"R_rule={report.R_rule:.2f}")
    print(json.dumps(report.to_dict()["axes"], ensure_ascii=False, indent=1))
    return 0


def cmd_styles(_args) -> int:
    from miidi.skills.loader import available_styles
    print("\n".join(available_styles()))
    return 0


def cmd_evaluate(args) -> int:
    from miidi.eval.score import evaluate_rules
    from miidi.schema.model import Composition
    raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
    try:
        comp = Composition.model_validate(raw)
    except ValidationError as exc:
        print(f"invalid composition: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evaluate_rules(comp).to_dict(), ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="miidi")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--style", required=True)
    g.add_argument("--prompt", required=True)
    g.add_argument("--out", default=None)
    g.add_argument("--rounds", type=int, default=2)
    g.add_argument("--no-review", action="store_true")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("styles")
    s.set_defaults(func=cmd_styles)

    e = sub.add_parser("evaluate")
    e.add_argument("--json", required=True)
    e.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

`src/miidi/__main__.py`:
```python
import sys

from miidi.cli import main

sys.exit(main())
```

`pyproject.toml`: add
```toml
[project.scripts]
miidi = "miidi.cli:main"
```

README usage section appended:
```markdown
## 命令行使用（配置好 .env 后）

    python -m miidi styles
    python -m miidi generate --style lofi --prompt "雨夜的咖啡馆" --out output/
    python -m miidi evaluate --json output/path/to/composition.json
```

- [ ] **Step 4: Verify pass + suite**
- [ ] **Step 5: Commit**

```bash
git add src/miidi/cli.py src/miidi/__main__.py pyproject.toml README.md tests/test_cli.py
git commit -m "feat: miidi CLI (generate/styles/evaluate)"
```

---

## Self-Review Notes (completed at plan time)

- Spec coverage: §5.1 四阶段→Tasks 5-6；§5.2 会话式修改→Task 6 revise；§5.3 曲风包→Tasks 2-3；§5.4 LLM 客户端→Task 1；§9.1 的脚本入口前置（CLI）→Task 7。Judge 轨与降级算子属 Plan 4（评测材料）。
- Cross-plan interface note: Plan 3 (webapp) consumes `run_pipeline/revise/SessionStore/PipelineResult`; Plan 4 consumes `evaluate_rules.to_dict`, `StylePack.defaults`, degrade operators (authored there).
- Known simplifications: structured-output knob deferred to Plan 4; revision routing covers 3 of 4 layers explicitly (structure routes through regenerate); context policy fixed at spec defaults.
