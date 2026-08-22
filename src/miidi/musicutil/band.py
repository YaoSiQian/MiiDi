from __future__ import annotations

import math


def band(x: float, lo0: float, lo1: float, hi1: float, hi0: float,
         floor: float = 0.0) -> float:
    if x <= lo0:
        return floor
    if x < lo1:
        return floor + (1.0 - floor) * (x - lo0) / (lo1 - lo0)
    if x <= hi1:
        return 1.0
    if x < hi0:
        return floor + (1.0 - floor) * (hi0 - x) / (hi0 - hi1)
    return floor


def norm_entropy(counts: list[int]) -> float:
    tot = sum(counts)
    if tot <= 0 or len(counts) <= 1:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / tot
            h -= p * math.log(p)
    return h / math.log(len(counts))
