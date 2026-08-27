#!/usr/bin/env python3
"""Analyze Touhou MIDI files and produce a JSON report for skill pack optimization."""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mido
import mido.midifiles.meta as _meta
import types as _types

# Patch mido's key_signature decoder to tolerate malformed files (empty data).
_spec_ks = _meta._META_SPECS[89]
_orig_ks_decode = _spec_ks.decode

def _tolerant_ks_decode(self_msg, msg, data):
    if len(data) < 2:
        msg.key = "C"
        return
    key = _meta.signed("byte", data[0])
    mode = data[1]
    try:
        msg.key = _meta._key_signature_decode[(key, mode)]
    except KeyError:
        msg.key = "C"

_spec_ks.decode = _types.MethodType(_tolerant_ks_decode, _spec_ks)


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
