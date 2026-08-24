# Lofi Style

## Identity
Hazy bedroom-produced chillhop at 66-92 BPM: sparse texture, dusty Rhodes chords
in maj7/min7/9 colors, and a lazy swung drum groove that drags just behind the
beat. Imperfection is the aesthetic — soft dynamics, few notes, deep calm.

## Workflow
- Planning stage reads: harmony.md (progressions), instruments.md (palette).
- Composition stage reads: rhythm.md (lazy swing grids), instruments.md (registers).
- Never read files not listed for your stage.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
