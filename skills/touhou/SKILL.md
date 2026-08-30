# Touhou Style

## Identity
High-energy doujin electronic rock at 120-170 BPM: multi-layered harmonic beds
(strings + harpsichord + piano + organ) stacked for dense chord pads, synth bass
with locked 8th-note drive, and square/saw leads carrying bright minor-key
melodies. Straight 16th drive, zero swing, relentless energy from first bar to
last. Cadences land on hard authentic closes (E7-Am) with full-band accent.

## Workflow
- Planning stage: design tempo, key, sections, chords, and instrument roster.
- Composition stage: write each track's notes over the full structure.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
