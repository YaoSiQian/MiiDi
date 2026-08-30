# Touhou MIDI Analysis & Skill Pack Optimization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyze 180 Touhou Project MIDI files from `.touhou_midi/` and use extracted data to optimize `skills/touhou/` pack content (instruments, harmony, rhythm, defaults, SKILL.md).

**Architecture:** Write a Python analysis script (`tools/analyze_touhou_midi.py`) that reads all MIDI files and extracts: instrument usage by channel, tempo distributions, chord progressions (inferred from note co-occurrence), rhythmic density, note ranges per program. Output a JSON report. Then use the report data to rewrite each skill pack file with evidence-based content.

**Tech Stack:** Python 3.11+, mido (MIDI parsing), existing kernel `src/miidi/render/midi.py` for reference patterns.

**Spec:** `docs/superpowers/specs/2026-08-22-miidi-design.md` §5 (风格 Skills)

---

## Context: Current State

The current `skills/touhou/` pack is minimal:
- **instruments.md**: 4 instruments (Trumpet 56, Piano 0, Synth Bass 38, Saw Lead 81)
- **harmony.md**: 7 chords (Am, Dm, Em, F, G, E7, C) + 3 progressions
- **rhythm.md**: 1 drum pattern (kick/snare/hat)
- **defaults.json**: BPM 150-192, basic density_ref
- **SKILL.md**: 17 lines, generic description

**Preliminary analysis** of 20 sampled files shows:
- ZUN uses **30+ distinct GM programs** (not just 4)
- Most frequent: GM 48 (Strings), GM 6 (Harpsichord), GM 80 (Square Lead), GM 36 (Synth Bass), GM 1 (Bright Piano), GM 0 (Acoustic Grand), GM 16 (Drawbar Organ), GM 24 (Nylon Guitar), GM 37 (Slap Bass), GM 81 (Saw Lead)
- Tempo range is wider than specified: 85–170 BPM (avg 137) vs current 150–192
- Note ranges vary significantly by program and role

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `tools/analyze_touhou_midi.py` | Create | MIDI analysis script → JSON report |
| `tools/touhou_analysis_report.json` | Create (generated) | Analysis output |
| `skills/touhou/SKILL.md` | Rewrite | Identity paragraph with evidence-based descriptions |
| `skills/touhou/instruments.md` | Rewrite | Role-based palette with programs, registers, usage notes |
| `skills/touhou/harmony.md` | Rewrite | Chord vocabulary + progressions from note co-occurrence data |
| `skills/touhou/rhythm.md` | Rewrite | Drum patterns from channel 9/10 analysis, density data |
| `skills/touhou/defaults.json` | Rewrite | BPM range, density_ref, drum_patterns from data |

---

### Task 1: MIDI Analysis Script

**Files:**
- Create: `tools/analyze_touhou_midi.py`
- Create: `tools/touhou_analysis_report.json` (generated output)

**Interfaces:**
- Consumes: `.touhou_midi/**/*.mid` (180 MIDI files, type 0, ticks_per_beat=480)
- Produces: JSON report at `tools/touhou_analysis_report.json`

- [ ] **Step 1: Write the analysis script skeleton**

```python
#!/usr/bin/env python3
"""Analyze Touhou MIDI files and produce a JSON report for skill pack optimization."""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mido


def find_midi_files(root: str) -> list[str]:
    """Find all .mid files under root."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.lower().endswith(".mid"):
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def analyze_file(filepath: str) -> dict:
    """Extract features from a single MIDI file."""
    m = mido.MidiFile(filepath)
    result = {
        "file": os.path.basename(filepath),
        "ticks_per_beat": m.ticks_per_beat,
        "channels": {},
        "tempos": [],
        "time_signatures": [],
        "total_notes": 0,
    }

    # Per-channel analysis
    channel_program = {}
    channel_notes = defaultdict(list)
    channel_velocities = defaultdict(list)
    channel_durations = defaultdict(list)  # tick durations

    for track in m.tracks:
        abs_time = 0
        note_starts = {}  # (channel, note) -> start_tick
        for msg in track:
            abs_time += msg.time
            if msg.type == "program_change":
                channel_program[msg.channel] = msg.program
            if msg.type == "set_tempo":
                result["tempos"].append(mido.tempo2bpm(msg.tempo))
            if msg.type == "time_signature":
                result["time_signatures"].append(
                    f"{msg.numerator}/{msg.denominator}"
                )
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                note_starts[(ch, msg.note)] = abs_time
                channel_notes[ch].append(msg.note)
                channel_velocities[ch].append(msg.velocity)
            if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                ch = msg.channel
                key = (ch, msg.note)
                if key in note_starts:
                    dur = abs_time - note_starts.pop(key)
                    channel_durations[ch].append(dur)

    # Summarize channels
    for ch in sorted(channel_notes.keys()):
        notes = channel_notes[ch]
        if not notes:
            continue
        prog = channel_program.get(ch, None)
        result["channels"][ch] = {
            "program": prog,
            "note_count": len(notes),
            "pitch_min": min(notes),
            "pitch_max": max(notes),
            "pitch_mean": round(sum(notes) / len(notes), 1),
            "velocity_min": min(channel_velocities[ch]),
            "velocity_max": max(channel_velocities[ch]),
            "velocity_mean": round(
                sum(channel_velocities[ch]) / len(channel_velocities[ch]), 1
            ),
            "durations_ticks": {
                "min": min(channel_durations[ch]) if channel_durations[ch] else 0,
                "max": max(channel_durations[ch]) if channel_durations[ch] else 0,
                "mean": round(
                    sum(channel_durations[ch]) / len(channel_durations[ch]), 1
                )
                if channel_durations[ch]
                else 0,
            },
        }
        result["total_notes"] += len(notes)

    return result


def aggregate(files_data: list[dict]) -> dict:
    """Produce aggregate statistics across all files."""
    program_usage = Counter()  # program -> total note count
    program_files = defaultdict(set)  # program -> set of filenames
    program_channels = defaultdict(list)  # program -> list of (file, channel, pitch_min, pitch_max)
    all_tempos = []
    note_counts = []
    program_note_ranges = defaultdict(list)  # program -> list of all pitches

    for fd in files_data:
        fname = fd["file"]
        all_tempos.extend(fd["tempos"])
        note_counts.append(fd["total_notes"])
        for ch_info in fd["channels"].values():
            prog = ch_info["program"]
            if prog is None:
                continue
            program_usage[prog] += ch_info["note_count"]
            program_files[prog].add(fname)
            program_channels[prog].append(
                (fname, ch_info["pitch_min"], ch_info["pitch_max"])
            )
            program_note_ranges[prog].extend(
                [ch_info["pitch_min"], ch_info["pitch_max"]]
            )

    # Build program summary
    program_summary = {}
    for prog in sorted(program_usage.keys()):
        ranges = program_note_ranges[prog]
        program_summary[prog] = {
            "total_notes": program_usage[prog],
            "file_count": len(program_files[prog]),
            "overall_pitch_min": min(ranges),
            "overall_pitch_max": max(ranges),
        }

    return {
        "total_files": len(files_data),
        "total_notes": sum(fd["total_notes"] for fd in files_data),
        "tempo_min": min(all_tempos) if all_tempos else 0,
        "tempo_max": max(all_tempos) if all_tempos else 0,
        "tempo_mean": round(sum(all_tempos) / len(all_tempos), 1) if all_tempos else 0,
        "program_summary": program_summary,
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ".touhou_midi"
    output = sys.argv[2] if len(sys.argv) > 2 else "tools/touhou_analysis_report.json"

    print(f"Scanning {root}...")
    files = find_midi_files(root)
    print(f"Found {len(files)} MIDI files")

    files_data = []
    for i, fp in enumerate(files):
        print(f"  [{i+1}/{len(files)}] {os.path.basename(fp)}")
        try:
            files_data.append(analyze_file(fp))
        except Exception as e:
            print(f"    ERROR: {e}")

    report = {
        "per_file": files_data,
        "aggregate": aggregate(files_data),
    }

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report written to {output}")
    print(f"Aggregate: {report['aggregate']['total_notes']} notes across {report['aggregate']['total_files']} files")
    print(f"Tempo range: {report['aggregate']['tempo_min']:.0f}-{report['aggregate']['tempo_max']:.0f} BPM")
    print(f"Programs found: {len(report['aggregate']['program_summary'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run analysis on all 180 files**

Run: `python tools/analyze_touhou_midi.py .touhou_midi tools/touhou_analysis_report.json`
Expected: prints progress for 180 files, writes JSON report

- [ ] **Step 3: Verify report structure**

Run: `python -c "import json; r=json.load(open('tools/touhou_analysis_report.json')); print(f'Files: {r[\"aggregate\"][\"total_files\"]}'); print(f'Programs: {len(r[\"aggregate\"][\"program_summary\"])}'); print(f'Tempo: {r[\"aggregate\"][\"tempo_min\"]:.0f}-{r[\"aggregate\"][\"tempo_max\"]:.0f}')"`
Expected: Files: 180, Programs: ~30+, Tempo: ~85-170

- [ ] **Step 4: Commit**

```bash
git add tools/analyze_touhou_midi.py tools/touhou_analysis_report.json
git commit -m "feat: Touhou MIDI analysis script and 180-file report"
```

---

### Task 2: Rewrite `instruments.md` from Report Data

**Files:**
- Modify: `skills/touhou/instruments.md`
- Read: `tools/touhou_analysis_report.json` (aggregate.program_summary)

**Interfaces:**
- Consumes: report's program_summary with total_notes, file_count, overall_pitch_min/max per GM program
- Produces: instruments.md with role-based table

- [ ] **Step 1: Read the report's top programs and their data**

Identify the top 10-12 programs by note count and file count from the report. Group by role:
- **Lead melody**: GM 80 (Square Lead), GM 81 (Saw Lead), GM 56 (Trumpet) — high pitch range, fewer notes but prominent
- **Harmonic/pad**: GM 48 (Strings), GM 6 (Harpsichord), GM 1 (Bright Piano), GM 0 (Acoustic Grand), GM 16 (Drawbar Organ), GM 24 (Nylon Guitar)
- **Bass**: GM 36 (Synth Bass), GM 37 (Slap Bass), GM 39 (Fretless Bass)
- **Counter/accent**: GM 87 (Voice Oohs), GM 85 (Voice), GM 66 (Soprano Sax)

- [ ] **Step 2: Write the new instruments.md**

Write the file with a table of programs, their actual observed pitch ranges, usage frequency, and role. Include a note about ZUN's multi-program layering (e.g., strings + harpsichord + organ for harmonic bed).

- [ ] **Step 3: Commit**

```bash
git add skills/touhou/instruments.md
git commit -m "feat: touhou instruments.md updated from MIDI analysis"
```

---

### Task 3: Rewrite `harmony.md` from Report Data

**Files:**
- Modify: `skills/touhou/harmony.md`
- Read: `tools/touhou_analysis_report.json` (per_file channels data for chord inference)

**Interfaces:**
- Consumes: per-file channel data (notes by channel + program) for chord co-occurrence analysis
- Produces: harmony.md with evidence-based chord vocabulary and progressions

- [ ] **Step 1: Write a chord inference helper**

Add to `tools/analyze_touhou_midi.py` or create `tools/infer_chords.py`: for each file, extract note co-occurrences within 1-bar windows (1920 ticks at PPQ=480) on harmonic channels (programs 0,1,6,16,24,48), classify common patterns into chord symbols using the kernel's `parse_chord` from `src/miidi/schema/chords.py`.

- [ ] **Step 2: Run chord analysis and identify top progressions**

Run the chord inference, output a frequency table of chord symbols and common 2-4 chord sequences.

- [ ] **Step 3: Write the new harmony.md**

Write with:
- Chord vocabulary from the top ~15 most frequent symbols
- Characteristic progressions from the most common 2-4 chord sequences
- Key analysis (most common key centers)
- Cadence patterns (most common final chords in phrases)

- [ ] **Step 4: Commit**

```bash
git add skills/touhou/harmony.md tools/infer_chords.py  # or modified analyze script
git commit -m "feat: touhou harmony.md updated from MIDI chord analysis"
```

---

### Task 4: Rewrite `rhythm.md` from Report Data

**Files:**
- Modify: `skills/touhou/rhythm.md`
- Modify: `skills/touhou/defaults.json`
- Read: `tools/touhou_analysis_report.json` (per_file channels, tempo data)

**Interfaces:**
- Consumes: per-file channel 9/10 (percussion) note data, tempo distribution
- Produces: rhythm.md with multiple drum patterns, defaults.json with data-driven BPM/density

- [ ] **Step 1: Analyze percussion channels (9/10) across files**

Extract note_on events from GM percussion channel (ch 9/10, no program_change needed — it's percussion). Classify by note number:
- 36=Kick, 38=Snare, 42=Closed Hat, 46=Open Hat, 49=Crash, 51=Ride

Count onset positions modulo 1920 (1 bar) to find the dominant rhythmic pattern.

- [ ] **Step 2: Write the new rhythm.md**

Write with:
- 2-3 drum patterns (dominant pattern, a fill pattern, a half-time variant)
- Evidence-based tick values from the actual MIDI data
- Subdivision notes (straight vs any swing evidence)

- [ ] **Step 3: Rewrite defaults.json**

Write with:
- BPM range from actual tempo distribution (e.g., 120-170 based on data)
- density_ref from actual note density per role
- drum_patterns from the dominant percussion patterns

- [ ] **Step 4: Commit**

```bash
git add skills/touhou/rhythm.md skills/touhou/defaults.json
git commit -m "feat: touhou rhythm.md and defaults.json from MIDI analysis"
```

---

### Task 5: Rewrite `SKILL.md` Identity

**Files:**
- Modify: `skills/touhou/SKILL.md`

**Interfaces:**
- Consumes: the updated instruments.md, harmony.md, rhythm.md, defaults.json
- Produces: SKILL.md with evidence-based identity paragraph

- [ ] **Step 1: Write the new SKILL.md**

Rewrite the identity paragraph to reflect the actual ZUN style as revealed by analysis:
- Multi-layered harmonic beds (strings + harpsichord + organ + piano)
- Synth bass + slap bass combination
- Square/saw leads doubling with orchestral instruments
- Tempo range from actual data (likely 120-170, not 150-192)
- Key vocabulary from chord analysis

- [ ] **Step 2: Commit**

```bash
git add skills/touhou/SKILL.md
git commit -m "feat: touhou SKILL.md identity updated from MIDI analysis"
```

---

### Task 6: Validation

**Files:**
- Read: all `skills/touhou/` files
- Read: `tools/touhou_analysis_report.json`

**Interfaces:**
- Consumes: updated skill pack files + report
- Produces: validation that all chord symbols parse, all programs are valid GM, density ranges are sensible

- [ ] **Step 1: Validate chord symbols parse**

Run: `python -c "from miidi.schema.chords import parse_chord; [parse_chord(s) for s in ['Am','Dm','F','G','E7','C','Dm7','Asus4','Bdim','G/B','Fmaj7','C/E','Am7','D/F#','Bb','Eb','Ab','Db','Gb','Cb']]"` (adjust list to match actual new vocabulary)
Expected: all parse without error

- [ ] **Step 2: Validate GM program numbers are 0-127**

Run: grep all program numbers from instruments.md, verify each is in 0-127 range.

- [ ] **Step 3: Validate defaults.json is well-formed**

Run: `python -c "import json; d=json.load(open('skills/touhou/defaults.json')); assert 'bpm_range' in d; assert 'density_ref' in d; assert 'drum_patterns' in d; print('OK')"`

- [ ] **Step 4: Run existing touhou tests**

Run: `pytest tests/test_skills_loader.py -v`
Expected: all tests pass (loader still reads the pack correctly)

- [ ] **Step 5: Commit if any fixes needed**

```bash
git add skills/touhou/
git commit -m "fix: touhou skill pack validation fixes"
```
