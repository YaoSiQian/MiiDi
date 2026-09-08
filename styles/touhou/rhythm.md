# Rhythmic Feel

Relentless straight 16th drive at 120-170 BPM, no swing offsets. The kick
doubles the piano arpeggio accents with a double-hit flare into beat 3 and the
bar line; hats mark every 8th to keep the chorus energy pinned. Percussion
analysis of 152 files confirms closed hi-hat as the dominant voice (134K events),
followed by kick (99K) and snare (77K).

## Drum Patterns

One bar = 1920 ticks (ppq=480); grid steps are 16ths (120 ticks each).

### Main Drive (dominant pattern)

```
step:   1e&u2e&u3e&u4e&u
kick:   x...x..x.x...x..    ticks [0, 360, 720, 1080, 1440, 1800]
snare:  ....x.......x...    ticks [480, 1440]
hat:    x.x.x.x.x.x.x.x.    ticks [0, 240, 480, 720, 960, 1200, 1440, 1680]
```

### Fill Variant (section transitions)

```
step:   1e&u2e&u3e&u4e&u
kick:   x...............    ticks [0]
snare:  ....x..x..x..x..    ticks [480, 720, 960, 1200]
hat:    x.x.x.x.x.x.x.x.    ticks [0, 240, 480, 720, 960, 1200, 1440, 1680]
crash:  x...............    ticks [0]
```

### Half-Time Variant (verses, quieter sections)

```
step:   1e&u2e&u3e&u4e&u
kick:   x.......x.......    ticks [0, 960]
snare:  .......x.......    ticks [960]
hat:    x.x.x.x.x.x.x.x.    ticks [0, 240, 480, 720, 960, 1200, 1440, 1680]
```

## Grid Notes

Subdivision policy: melody runs in straight 16ths and syncopated 8ths starting on
any step; piano arpeggios cycle on 8th or 16th positions without pause; bass
locks to the kick. No swing offsets — every onset sits exactly on its integer
tick; intensity comes from density and velocity contrast, never from placement.

## Percussion Evidence

From 152 analyzed files (180 total; 28 had format errors):
- Closed hi-hat: 133,882 events — the rhythmic backbone
- Kick: 99,417 events — strong on beats 1 and 3, with syncopated doubles
- Snare: 77,171 events — primarily on beats 2 and 4
- Open hi-hat: 50,614 events — accents and off-beat lifts
- Crash: 9,949 events — section entrances
- Ride: 9,132 events — alternative to hi-hat in some pieces

Tom fills (high: 12K, low: 9K, mid: 4K) appear at transitions. Tambourine
(3K) adds color in select arrangements.
