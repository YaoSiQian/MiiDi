# Pop Style

## Identity
Bright four-piece band idiom: drums, electric bass, piano or guitar comping, and a
single memorable lead. Diatonic major/minor vocabulary built around the I-V-vi-IV
family, clear phrase structure, and steady backbeat energy.

## Workflow
- Planning stage: design tempo, key, sections, chords, and instrument roster.
- Composition stage: write each track's notes over the full structure.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
