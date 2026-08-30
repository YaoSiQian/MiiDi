# Two-Phase Review: Arrangement Coordination + Per-Track Refinement

**Date**: 2026-08-28
**Status**: Draft
**Scope**: Pipeline review stage — `pipeline/orchestrator.py`, `pipeline/stages.py`, `pipeline/prompts.py`

## Problem

The current `self_review` does per-track patching: evaluate full composition → LLM picks ONE track → rewrite its notes. This misses arrangement-level issues:

- **Frequency balance** — two tracks competing in the same register
- **Sectional density** — sections too busy or too sparse
- **Role clarity** — multiple tracks competing for melodic attention
- **Redundancy** — two tracks playing similar rhythms/pitches

A real music producer fixes these *structural* issues before touching individual notes.

## Design

### Two-Phase Pipeline

```
Current:
  compose all tracks → self_review (patch notes) → done

New:
  compose all tracks → arrange_coordinate (structural decisions)
                     → apply adjustments (programmatic)
                     → self_review (fine-grained note fixes)
                     → done
```

### Phase 1: Arrangement Coordinator

**LLM Role**: Music arranger making structural decisions about which tracks play when.

**Input**: Full composition (all tracks, all sections)
**Output**: JSON array of adjustment commands

**Analysis Framework** (in the prompt):
1. **Frequency Balance** — MIDI register per track: Bass (24-48), Mid (48-72), High (72-96)
2. **Sectional Density** — Notes per bar: Sparse (<4), Normal (4-12), Dense (>12)
3. **Role Clarity** — Is ONE track clearly the melodic focus per section?
4. **Redundancy** — Are two tracks playing similar rhythms/pitches?

**Adjustment Commands** (what the LLM outputs):

| Command | Parameters | Effect |
|---------|-----------|--------|
| `section_mute` | track, start_bar, end_bar | Remove all notes in bar range |
| `octave_shift` | track, direction (up/down) | Transpose ±12 semitones |
| `density_reduce` | track, start_bar, end_bar, factor | Keep every Nth note (factor=0.5 → half) |

**Output Schema**:

```json
{
  "analysis": {
    "<section_name>": {
      "frequency_balance": "description",
      "density": "sparse|normal|dense",
      "role_clarity": "description",
      "redundancy": "description"
    }
  },
  "adjustments": [
    {"action": "section_mute", "track": "Counter", "start_bar": 12, "end_bar": 20},
    {"action": "octave_shift", "track": "Harmony", "direction": "down"},
    {"action": "density_reduce", "track": "Color", "start_bar": 0, "end_bar": 8, "factor": 0.5}
  ]
}
```

### Phase 2: Command Applicator (programmatic)

`apply_adjustments(comp, adjustments)` — applies commands to the composition:

- `section_mute`: filters notes where `start_bar * 1920 <= onset < end_bar * 1920`
- `octave_shift`: adds ±12 to all pitches
- `density_reduce`: keeps every `(1/factor)`-th note in the bar range

No LLM call — deterministic transformation.

### Phase 3: Per-Track Refinement (existing)

`self_review()` runs on the coordinated arrangement, doing fine-grained note fixes.

### LLM Prompt Design

**Why this works for the LLM:**
1. **Concrete analysis framework** — 4 dimensions with clear thresholds, not abstract "fix the music"
2. **Machine-executable outputs** — commands, not free text
3. **No note rewriting** — coordinator only decides *which tracks play when*
4. **Separation of concerns** — musical judgment (LLM) vs mechanical transformation (code)

### Files Changed

| File | Changes |
|------|---------|
| `pipeline/prompts.py` | Add `arrange_coordinate_system()`, `arrange_coordinate_user()` |
| `pipeline/stages.py` | Add `arrange_coordinate()`, `apply_adjustments()` |
| `pipeline/orchestrator.py` | Insert arrangement phase between arrange stage and self_review |

### Integration Point

In `orchestrator.py`, after the arrange stage completes and before self_review:

```python
# Phase 1: Arrangement coordination
adjustments = arrange_coordinate(client, comp)
comp = apply_adjustments(comp, adjustments)
log.append(f"arrangement: {len(adjustments)} adjustments applied")

# Phase 2: Per-track refinement (existing self_review)
reviewed, trajectory = self_review(client, comp, pack.defaults)
```

### Impact on Pipeline Timing

| Stage | Current | With Coordination |
|-------|---------|-------------------|
| plan | 1 LLM call | 1 LLM call (unchanged) |
| core | 3 LLM calls | 3 LLM calls (unchanged) |
| arrange | 3 LLM calls | 3 LLM calls (unchanged) |
| **arrange_coordinate** | — | **1 new LLM call** |
| self_review | 1-2 LLM calls | 1-2 LLM calls (unchanged) |
| **Total** | **8-10 calls** | **9-11 calls** (+1 for coordination) |

The +1 LLM call for coordination is offset by better quality — fewer self_review rounds needed because structural issues are already resolved.

### Testing

- Unit test `apply_adjustments()` with known inputs
- Integration test: run full pipeline with coordination enabled
- Verify existing 200 tests still pass (no regressions)
