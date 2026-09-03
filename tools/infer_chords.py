#!/usr/bin/env python3
"""Infer chord vocabulary from Touhou MIDI files via note co-occurrence analysis."""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mido

from midi_utils import find_midi_files

# Add project root to path for schema import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.miidi.schema.chords import parse_chord, ChordParseError

# MIDI note name mapping
_PC_TO_NAME = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Programs considered "harmonic" (voice-leading / chord carriers)
HARMONIC_PROGRAMS = {0, 1, 3, 4, 5, 6, 7, 8, 16, 24, 25, 26, 48, 49}

# Chord templates to try (root + quality suffix matching parse_chord)
CHORD_TEMPLATES = [
    ("", (0, 4, 7)),       # major
    ("m", (0, 3, 7)),      # minor
    ("7", (0, 4, 7, 10)),  # dom7
    ("m7", (0, 3, 7, 10)), # min7
    ("dim", (0, 3, 6)),    # dim
    ("sus4", (0, 5, 7)),   # sus4
]


def pcs_from_pitches(pitches: list[int]) -> frozenset[int]:
    return frozenset(p % 12 for p in pitches)


def classify_chord(pcs: frozenset[int]) -> str | None:
    """Try to match a set of pitch classes to a chord symbol."""
    if len(pcs) < 3:
        return None
    best = None
    best_score = 0
    for root_pc in range(12):
        for suffix, template in CHORD_TEMPLATES:
            template_set = frozenset((root_pc + iv) % 12 for iv in template)
            if template_set <= pcs:
                score = len(template_set)
                if score > best_score:
                    best_score = score
                    best = _PC_TO_NAME[root_pc] + suffix
    return best


def extract_chords_from_file(filepath: str) -> list[str]:
    """Extract chord symbols from a single MIDI file using 1-bar windows."""
    m = mido.MidiFile(filepath)
    ppq = m.ticks_per_beat
    bar_ticks = ppq * 4  # 4/4 time

    # Collect note events with absolute times
    channel_program = {}
    notes_by_channel = defaultdict(list)  # channel -> [(abs_time, pitch)]

    for track in m.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == "program_change":
                channel_program[msg.channel] = msg.program
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                prog = channel_program.get(ch, None)
                if prog is not None and prog in HARMONIC_PROGRAMS:
                    notes_by_channel[ch].append((abs_time, msg.note))

    # Aggregate all harmonic notes into bar windows
    all_notes = []
    for ch_notes in notes_by_channel.values():
        all_notes.extend(ch_notes)
    all_notes.sort(key=lambda x: x[0])

    if not all_notes:
        return []

    # Determine total length
    max_time = all_notes[-1][0] if all_notes else 0
    num_bars = max(1, max_time // bar_ticks + 1)

    chords = []
    for bar_idx in range(num_bars):
        bar_start = bar_idx * bar_ticks
        bar_end = bar_start + bar_ticks
        pitches_in_bar = [p for t, p in all_notes if bar_start <= t < bar_end]
        if len(pitches_in_bar) >= 3:
            pcs = pcs_from_pitches(pitches_in_bar)
            symbol = classify_chord(pcs)
            if symbol:
                chords.append(symbol)

    return chords


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ".touhou_midi"
    output = sys.argv[2] if len(sys.argv) > 2 else "tools/chord_analysis.json"

    print(f"Scanning {root} for chord analysis...")
    files = find_midi_files(root)
    print(f"Found {len(files)} MIDI files")

    chord_counter = Counter()
    progression_counter = Counter()  # 2-chord sequences
    file_chords = {}

    for i, fp in enumerate(files):
        fname = os.path.basename(fp)
        print(f"  [{i+1}/{len(files)}] {fname}")
        try:
            chords = extract_chords_from_file(fp)
            if chords:
                file_chords[fname] = chords
                for c in chords:
                    chord_counter[c] += 1
                for j in range(len(chords) - 1):
                    progression_counter[(chords[j], chords[j + 1])] += 1
        except Exception as e:
            print(f"    ERROR: {e}")

    # Top progressions (2-chord)
    top_progressions = [
        {"from": k[0], "to": k[1], "count": v}
        for k, v in progression_counter.most_common(20)
    ]

    # 3-chord and 4-chord sequences
    three_chord = Counter()
    four_chord = Counter()
    for chords in file_chords.values():
        for j in range(len(chords) - 2):
            three_chord[(chords[j], chords[j + 1], chords[j + 2])] += 1
        for j in range(len(chords) - 3):
            four_chord[(chords[j], chords[j + 1], chords[j + 2], chords[j + 3])] += 1

    result = {
        "chord_frequencies": dict(chord_counter.most_common(30)),
        "top_progressions_2": top_progressions,
        "top_progressions_3": [
            {"chords": list(k), "count": v}
            for k, v in three_chord.most_common(15)
        ],
        "top_progressions_4": [
            {"chords": list(k), "count": v}
            for k, v in four_chord.most_common(10)
        ],
        "files_analyzed": len(files),
        "files_with_chords": len(file_chords),
    }

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nChord analysis written to {output}")
    print(f"Top chords: {chord_counter.most_common(10)}")
    print(f"Top 2-chord progressions: {top_progressions[:5]}")


if __name__ == "__main__":
    main()
