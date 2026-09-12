"""评测实验共用的统计量：带并列秩的 Spearman 等级相关（无第三方依赖）。"""

from __future__ import annotations


def _average_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    if den == 0:
        return None
    return num / den


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 等级相关；常值序列或长度不足返回 None。"""
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return None
    return pearson(_average_ranks(xs), _average_ranks(ys))
