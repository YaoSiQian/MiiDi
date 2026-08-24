# Touhou Style

## Identity
High-energy doujin denpa-rock at fast tempo (150-192 BPM): a soaring trumpet lead
on program 56 over driving piano arpeggios on program 0, with high chorus energy
pushed from first bar to last. Straight 16th drive, bright minor keys, zero chill.

## Workflow
- Planning stage reads: harmony.md (progressions), instruments.md (palette).
- Composition stage reads: rhythm.md (drive grids), instruments.md (registers).
- Never read files not listed for your stage.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
