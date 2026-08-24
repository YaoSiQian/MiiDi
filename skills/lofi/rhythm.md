# Rhythmic Feel

Slow head-nod groove at 66-92 BPM: lazy swung drums placed slightly behind the
grid, offbeat 8ths delayed by the style's swing offsets (180 ticks). Everything
feels a half-step late in the best way.

## Drum Patterns

One bar = 1920 ticks; grid steps are 16ths (120 ticks each). Onsets below are
exact tick positions from defaults.json — note the deliberately late kick and
the snare dragged past beat 4's step.

```
step:   1e&u2e&u3e&u4eu  (step = tick/120)
kick:   x.......x~......    ticks [0, 1020]              (~ hit drags to 1020, between steps 8-9)
snare:  ....x........x..    ticks [480, 1560]            (backbeat dragged to step 13)
hat:    .x...x...x...x..    ticks [120, 600, 1080, 1560] (swung offbeat 8ths)
```

## Grid Notes

Subdivision policy: melody uses sparse 8th/quarter phrasing with rests as gaps;
harmony pads hold long durations; bass lands on downbeats only. Swing offsets:
offbeat eighth positions are delayed by +180 ticks when written (tick 240 becomes
420), giving the drums their signature stumble.
