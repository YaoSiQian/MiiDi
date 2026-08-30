# Two-Phase Review Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add arrangement coordination phase before per-track self-review, enabling structural decisions (mute, octave shift, density reduction) before note-level fixes.

**Architecture:** New `arrange_coordinate()` LLM call outputs structured adjustment commands; `apply_adjustments()` applies them programmatically; existing `self_review()` runs on the coordinated result.

**Tech Stack:** Python, pydantic, httpx (existing)

**Spec:** `docs/superpowers/specs/2026-08-28-two-phase-review-design.md`

## Global Constraints

- Python ≥3.11, pydantic v2
- LLM timeout 300s per request
- `compose_track()` has up to 3 retries per track
- 200 existing tests must pass
- No changes to LLM client or session store

---

### Task 1: Add Arrangement Coordinator Prompts

**Files:**
- Modify: `src/miidi/pipeline/prompts.py`

**Interfaces:**
- Consumes: `StylePack` (for style context)
- Produces: `arrange_coordinate_system(pack)`, `arrange_coordinate_user(comp)` functions

- [ ] **Step 1: Add arrange_coordinate_system()**

Append to `prompts.py`:

```python
def arrange_coordinate_system(pack: StylePack) -> str:
    return (
        "You are an arrangement coordinator for a multi-track composition. "
        "Your job: identify coordination problems between tracks and output "
        "adjustment commands. You do NOT rewrite notes — you make structural "
        "decisions about the arrangement.\n\n"
        f"STYLE — {pack.name.title()}\n{_style_identity(pack)}\n\n"
        "ANALYSIS FRAMEWORK — for each section, assess:\n\n"
        "1. FREQUENCY BALANCE: Which MIDI register does each track occupy?\n"
        "   - Bass: C2-C4 (MIDI 24-48)\n"
        "   - Mid: C4-C6 (MIDI 48-72)\n"
        "   - High: C6-C8 (MIDI 72-96)\n"
        "   Are two non-bass tracks competing in the same register?\n\n"
        "2. SECTIONAL DENSITY: Count notes per bar per section.\n"
        "   - Sparse: <4 notes/bar (may need filling)\n"
        "   - Normal: 4-12 notes/bar\n"
        "   - Dense: >12 notes/bar (may need thinning)\n"
        "   Is the density appropriate for the section type?\n\n"
        "3. ROLE CLARITY: In each section, is ONE track clearly the melodic "
        "focus? Or are multiple tracks competing for attention?\n\n"
        "4. REDUNDANCY: Are two tracks playing similar rhythms or pitches "
        "in the same section?\n\n"
        "AVAILABLE ADJUSTMENT TOOLS:\n"
        "- section_mute: Silence a track in a specific bar range\n"
        "- octave_shift: Move a track up/down 12 semitones\n"
        "- density_reduce: Thin out notes in a section (factor=0.5 = keep half)\n\n"
        f"{_JSON_ONLY}"
    )
```

- [ ] **Step 2: Add arrange_coordinate_user()**

Append to `prompts.py`:

```python
def arrange_coordinate_user(comp_dict: dict) -> str:
    """Build user prompt from a composition dict."""
    import json
    tracks_info = []
    for t in comp_dict.get("tracks", []):
        notes = t.get("notes", [])
        bar_counts = {}
        for n in notes:
            bar = n[0] // 1920
            bar_counts[bar] = bar_counts.get(bar, 0) + 1
        pitches = [n[2] for n in notes] if notes else []
        pitch_range = f"{min(pitches)}-{max(pitches)}" if pitches else "N/A"
        tracks_info.append({
            "name": t.get("name", "?"),
            "role": t.get("role", "?"),
            "note_count": len(notes),
            "pitch_range": pitch_range,
            "bars_per_section": {f"bar{k}": v for k, v in sorted(bar_counts.items())[:16]},
        })

    sections = []
    cursor = 0
    for s in comp_dict.get("structure", []):
        bars = s.get("bars", 4)
        sections.append({"name": s.get("name"), "start_bar": cursor, "end_bar": cursor + bars})
        cursor += bars

    return (
        f"MUSICAL PLAN\n{json.dumps(comp_dict.get('meta', {}), indent=2)}\n\n"
        f"STRUCTURE\n{json.dumps(sections, indent=2)}\n\n"
        f"TRACKS\n{json.dumps(tracks_info, indent=2)}\n\n"
        "Analyze each section for frequency balance, density, role clarity, "
        "and redundancy. Output adjustment commands.\n\n"
        "OUTPUT SCHEMA:\n"
        '{"analysis": {"<section>": {"frequency_balance": "...", '
        '"density": "sparse|normal|dense", "role_clarity": "...", '
        '"redundancy": "..."}}, "adjustments": [{"action": "section_mute|'
        'octave_shift|density_reduce", "track": "<name>", ...}]}\n\n'
        f"{_JSON_ONLY}"
    )
```

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -q`
Expected: 200 tests pass (no regressions)

---

### Task 2: Add arrange_coordinate() and apply_adjustments()

**Files:**
- Modify: `src/miidi/pipeline/stages.py`

**Interfaces:**
- Consumes: `LLMClient`, `StylePack`, `Composition`
- Produces: `arrange_coordinate(client, pack, comp)` → `list[dict]`, `apply_adjustments(comp, adjustments)` → `Composition`

- [ ] **Step 1: Add apply_adjustments()**

Append to `stages.py`:

```python
def apply_adjustments(comp: Composition, adjustments: list[dict]) -> Composition:
    """Apply arrangement adjustment commands to a composition."""
    tracks = {t.name: t for t in comp.tracks}
    for adj in adjustments:
        action = adj.get("action")
        track_name = adj.get("track")
        track = tracks.get(track_name)
        if track is None:
            continue
        if action == "section_mute":
            start_tick = adj.get("start_bar", 0) * 1920
            end_tick = adj.get("end_bar", 999) * 1920
            track.notes = [n for n in track.notes
                          if n[0] < start_tick or n[0] >= end_tick]
        elif action == "octave_shift":
            direction = adj.get("direction", "up")
            shift = 12 if direction == "up" else -12
            track.notes = [[o, d, p + shift, v] for o, d, p, v in track.notes]
        elif action == "density_reduce":
            factor = adj.get("factor", 0.5)
            start_tick = adj.get("start_bar", 0) * 1920
            end_tick = adj.get("end_bar", 999) * 1920
            keep = max(1, int(1 / factor))
            new_notes = []
            count = 0
            for n in track.notes:
                if start_tick <= n[0] < end_tick:
                    count += 1
                    if count % keep == 0:
                        new_notes.append(n)
                else:
                    new_notes.append(n)
            track.notes = new_notes
    return comp
```

- [ ] **Step 2: Add arrange_coordinate()**

Append to `stages.py`:

```python
def arrange_coordinate(client: LLMClient, pack: StylePack,
                       comp: Composition) -> list[dict]:
    """Ask LLM to analyze arrangement and output adjustment commands."""
    from miidi.pipeline.prompts import (
        arrange_coordinate_system, arrange_coordinate_user,
    )
    system = arrange_coordinate_system(pack)
    user = arrange_coordinate_user(comp.model_dump())
    try:
        raw = client.respond_json(system, user)
    except Exception:
        return []
    adjustments = raw.get("adjustments", [])
    if not isinstance(adjustments, list):
        return []
    valid_actions = {"section_mute", "octave_shift", "density_reduce"}
    return [a for a in adjustments
            if isinstance(a, dict) and a.get("action") in valid_actions]
```

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -q`
Expected: 200 tests pass

---

### Task 3: Integrate into Pipeline Orchestrator

**Files:**
- Modify: `src/miidi/pipeline/orchestrator.py`

**Interfaces:**
- Consumes: `arrange_coordinate()`, `apply_adjustments()` from stages
- Produces: Updated `run_pipeline()` with arrangement phase

- [ ] **Step 1: Import new functions**

Add to imports in `orchestrator.py`:

```python
from miidi.pipeline.stages import (
    StageError, apply_adjustments, arrange_coordinate,
    build_context, compose_track, make_brief, self_review,
)
```

- [ ] **Step 2: Insert arrangement phase**

In `run_pipeline()`, after the arrange stage (`log.append("arrange: done")`) and before self_review, add:

```python
    # ── Phase 1: Arrangement coordination ──────────────────────
    try:
        adjustments = arrange_coordinate(client, pack, comp)
        if adjustments:
            comp = apply_adjustments(comp, adjustments)
            log.append(f"arrangement: {len(adjustments)} adjustments applied")
        else:
            log.append("arrangement: no adjustments needed")
    except Exception as exc:
        log.append(f"arrangement coordination failed: {exc}")

    # ── Phase 2: Self-review (per-track refinement) ───────────
```

This goes right before the existing `# ── Self-review ──` section.

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -q`
Expected: 200 tests pass

---

### Task 4: Add Unit Tests for apply_adjustments

**Files:**
- Create: `tests/test_arrangement.py`

**Interfaces:**
- Consumes: `apply_adjustments()` from stages
- Produces: Test coverage for adjustment commands

- [ ] **Step 1: Write test for section_mute**

```python
from miidi.pipeline.stages import apply_adjustments
from miidi.schema.model import Composition, Meta, Track, Key

def _make_comp(notes):
    return Composition(
        meta=Meta(title="Test", bpm=120, time_signature=[4,4],
                  key=Key(tonic_pc=0, mode="major"), style="pop"),
        structure=[{"name": "verse", "start_bar": 0, "bars": 4}],
        harmony=[],
        tracks=[Track(name="Lead", program=73, role="melody",
                      is_drum=False, notes=notes)],
    )

def test_section_mute():
    comp = _make_comp([
        [0, 480, 60, 100],      # bar 0
        [1920, 480, 62, 100],   # bar 1
        [3840, 480, 64, 100],   # bar 2
        [5760, 480, 65, 100],   # bar 3
    ])
    result = apply_adjustments(comp, [
        {"action": "section_mute", "track": "Lead", "start_bar": 1, "end_bar": 3}
    ])
    pitches = [n[2] for n in result.tracks[0].notes]
    assert 60 in pitches      # bar 0 kept
    assert 62 not in pitches  # bar 1 muted
    assert 64 not in pitches  # bar 2 muted
    assert 65 in pitches      # bar 3 kept
```

- [ ] **Step 2: Write test for octave_shift**

```python
def test_octave_shift():
    comp = _make_comp([[0, 480, 60, 100], [1920, 480, 72, 100]])
    result = apply_adjustments(comp, [
        {"action": "octave_shift", "track": "Lead", "direction": "down"}
    ])
    pitches = [n[2] for n in result.tracks[0].notes]
    assert pitches == [48, 60]
```

- [ ] **Step 3: Write test for density_reduce**

```python
def test_density_reduce():
    comp = _make_comp([
        [0, 120, 60, 100],
        [120, 120, 62, 100],
        [240, 120, 64, 100],
        [360, 120, 65, 100],
    ])
    result = apply_adjustments(comp, [
        {"action": "density_reduce", "track": "Lead",
         "start_bar": 0, "end_bar": 1, "factor": 0.5}
    ])
    assert len(result.tracks[0].notes) == 2
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_arrangement.py -v`
Expected: 3 tests pass

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: 203 tests pass (200 existing + 3 new)

---

### Task 5: Integration Test with Full Pipeline

**Files:**
- No file changes (verification only)

- [ ] **Step 1: Run full pipeline with coordination**

Start server, create session, verify arrangement phase appears in stage_log:

```bash
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"prompt":"a jazzy walking bass line","style":"jazz"}'
```

Check that stage_log contains "arrangement:" entries.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: 203+ tests pass

---

### Task 6: Final Verification

- [ ] **Step 1: Run full build and tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 2: Manual pipeline test**

Create a session and verify the arrangement coordinator produces valid adjustments:

```bash
# Check stage_log for arrangement entries
curl -s http://localhost:8000/api/sessions/{sid}/status | python -m json.tool
```
