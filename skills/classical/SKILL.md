# Classical Style

## Identity
Chamber-orchestral idiom built on functional harmony: clear tonic-dominant
polarities, voice-led part writing, and motivic development over steady phrase
periods. No drum track is used; pulse lives entirely in the notation of the
instruments themselves.

## Workflow
- Planning stage reads: harmony.md (progressions), instruments.md (palette).
- Composition stage reads: rhythm.md (meter and articulation), instruments.md (registers).
- Never read files not listed for your stage.

## Output Rules
Return ONLY JSON matching the requested schema. Onsets/durations are integer ticks
on the ppq=480 grid; rests are gaps between notes; chords inside one track are
same-onset duplicate pitches; velocity stays within 1-127 and varies musically
(never one flat value).
