# Jazz Style

## Identity
Small-combo swing idiom at 110-208 BPM: a ride-swing pulse, walking bass, and
comping pianos under a horn-led melody. Seventh chords are the default quality;
everything colors toward ii-V-I motion with a relaxed swing feel.

## Workflow
- Planning stage reads: harmony.md (progressions), instruments.md (palette).
- Composition stage reads: rhythm.md (swing grids), instruments.md (registers).
- Never read files not listed for your stage.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
