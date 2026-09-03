#!/usr/bin/env python3
"""Analyze percussion patterns from Touhou MIDI files on channel 9."""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mido

from midi_utils import find_midi_files

# GM Drum Map (note numbers)
DRUM_NAMES = {
    36: "kick", 35: "kick",
    38: "snare", 40: "snare_rim",
    42: "hat_closed", 44: "hat_pedal", 46: "hat_open",
    49: "crash", 51: "ride",
    45: "tom_low", 41: "tom_low", 43: "tom_floor",
    48: "tom_mid", 47: "tom_mid",
    50: "tom_high", 39: "tom_high",
    56: "cowbell", 54: "tambourine",
}

# Normalize note numbers to primary drum
DRUM_MAP = {
    35: 36, 36: 36,  # kick
    38: 38, 40: 38,  # snare
    42: 42, 44: 42,  # closed hat
    46: 46,  # open hat
    49: 49,  # crash
    51: 51,  # ride
    41: 41, 43: 41, 45: 41,  # low toms
    47: 47, 48: 47,  # mid toms
    39: 50, 50: 50,  # high toms
    54: 54, 56: 56,  # aux
}


def analyze_percussion(filepath: str) -> dict | None:
    """Extract percussion events from channel 9 of a MIDI file."""
    m = mido.MidiFile(filepath)
    ppq = m.ticks_per_beat
    bar_ticks = ppq * 4

    percussion_events = []  # (abs_time, note)

    for track in m.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == "note_on" and msg.velocity > 0 and msg.channel == 9:
                percussion_events.append((abs_time, msg.note))

    if not percussion_events:
        return None

    percussion_events.sort(key=lambda x: x[0])

    # Count occurrences by drum type
    drum_counts = Counter()
    # Count onset positions modulo bar_ticks for pattern analysis
    drum_positions = defaultdict(Counter)  # drum -> Counter(position_in_bar -> count)

    for t, note in percussion_events:
        mapped = DRUM_MAP.get(note, note)
        name = DRUM_NAMES.get(mapped, f"other_{mapped}")
        drum_counts[name] += 1
        pos_in_bar = t % bar_ticks
        drum_positions[name][pos_in_bar] += 1

    return {
        "ppq": ppq,
        "bar_ticks": bar_ticks,
        "total_events": len(percussion_events),
        "drum_counts": dict(drum_counts),
        "drum_positions": {
            name: dict(pos.most_common(20))
            for name, pos in drum_positions.items()
        },
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ".touhou_midi"
    output = sys.argv[2] if len(sys.argv) > 2 else "tools/percussion_analysis.json"

    print(f"Scanning {root} for percussion analysis...")
    files = find_midi_files(root)
    print(f"Found {len(files)} MIDI files")

    # Aggregate
    total_drum_counts = Counter()
    all_patterns = defaultdict(Counter)  # drum -> Counter(position -> total_count)
    file_results = []
    files_with_percussion = 0

    for i, fp in enumerate(files):
        fname = os.path.basename(fp)
        print(f"  [{i+1}/{len(files)}] {fname}")
        try:
            result = analyze_percussion(fp)
            if result:
                files_with_percussion += 1
                file_results.append({"file": fname, **result})
                for drum, count in result["drum_counts"].items():
                    total_drum_counts[drum] += count
                for drum, positions in result["drum_positions"].items():
                    for pos, count in positions.items():
                        all_patterns[drum][pos] += count
        except Exception as e:
            print(f"    ERROR: {e}")

    # Find dominant pattern for main drums
    ppq = 48  # typical from report
    bar_ticks = ppq * 4  # 192 ticks
    # Also compute for common ppq=480
    bar_ticks_480 = 480 * 4  # 1920

    # Normalize positions to a 1920-tick grid (ppq=480 standard)
    normalized_patterns = {}
    for drum, positions in all_patterns.items():
        norm_pos = Counter()
        for pos, count in positions.items():
            # Normalize from actual ppq to 480 ppq
            norm_tick = round(pos * (480 / ppq))
            norm_pos[norm_tick] += count
        normalized_patterns[drum] = dict(norm_pos.most_common(24))

    result = {
        "files_analyzed": len(files),
        "files_with_percussion": files_with_percussion,
        "total_drum_counts": dict(total_drum_counts.most_common()),
        "dominant_patterns_1920": normalized_patterns,
        "ppq_used": ppq,
    }

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nPercussion analysis written to {output}")
    print(f"Files with percussion: {files_with_percussion}/{len(files)}")
    print(f"Total drum counts: {total_drum_counts.most_common(10)}")
    for drum in ["kick", "snare", "hat_closed", "hat_open", "crash"]:
        if drum in normalized_patterns:
            top = sorted(normalized_patterns[drum].items(), key=lambda x: -x[1])[:5]
            print(f"  {drum} top positions: {top}")


if __name__ == "__main__":
    main()
