# Classical Style

## Identity
Chamber-orchestral idiom built on functional harmony: clear tonic-dominant
polarities, voice-led part writing, and motivic development over steady phrase
periods. No drum track is used; pulse lives entirely in the notation of the
instruments themselves.

## Workflow
- Planning stage: design tempo, key, sections, chords, and instrument roster.
- Composition stage: write each track's notes over the full structure.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
