# MiiDi Evaluation Method

## Overview

MiiDi uses a dual-track evaluation system:

1. **Rule Track** (deterministic): 6 axes + 4 gates → R_rule ∈ [0,100]
2. **Judge Track** (LLM-as-judge): 3 dimensions → J1, J2, J3 ∈ [0,100]

Composite: `0.6·R_rule + 0.4·mean(J1,J2,J3)`

## Rule Track Axes

| Axis | Weight | What it measures |
|------|--------|-----------------|
| A1 Format | gate | validate() pass/fail |
| A2 Harmony | 0.30 | Scale adherence, chord support, cluster rate |
| A3 Voice | 0.20 | Range fit, parallel motion, leap rate |
| A4 Rhythm | 0.20 | Grid adherence, density, drum patterns |
| A5 Structure | 0.20 | Coverage, similarity, motif recall |
| A6 Dynamics | 0.10 | Velocity spread, directionality |

## Anti-Degeneration Gates

- G_repetition: n-gram self-copy rate
- G_density: extreme density penalty
- G_balance: track content imbalance
- G_spread: fake register width

## Judge Track Dimensions

| Dimension | What it checks | Rubric |
|-----------|---------------|--------|
| J1 Style | Adherence to style features | yes/partial/no per feature |
| J2 Prompt | Following explicit requirements | satisfied/violated/unaddressed |
| J3 Musicality | Overall musical quality | 1-5 anchor rubric |

## Experiments

- E1 Discrimination: good/medium/bad tiers
- E2 Consistency: rule determinism + judge stability
- E3 Adversarial: cheat strategy detection
