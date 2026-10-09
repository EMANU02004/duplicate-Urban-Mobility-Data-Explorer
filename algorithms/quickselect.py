"""Quickselect-based quartiles and IQR outlier fences — written by hand.

Problem it solves: the cleaning stage needs Q1 and Q3 of ~3 million
fare-per-mile and speed values to flag outliers. Sorting the whole column
costs O(n log n); we only need two order statistics, which quickselect finds
in expected O(n) time without sorting.

No sort(), sorted(), statistics, numpy or pandas quantile functions are used
in this module.

Pseudo-code
-----------
    select(a, k):                      # k-th smallest, 0-based, in place
        lo, hi = 0, len(a) - 1
        while lo < hi:
            pivot = a[random index in lo..hi]
            three-way partition a[lo..hi] into  < pivot | == pivot | > pivot
                  giving boundaries lt, gt
            if k < lt:  hi = lt - 1        # answer is in the "less" block
            elif k > gt: lo = gt + 1       # answer is in the "greater" block
            else: return pivot             # k landed in the "equal" block
        return a[lo]

    quantile(a, q):                    # linear interpolation, like numpy's default
        pos = q * (n - 1);  i = floor(pos);  frac = pos - i
        low = select(a, i)
        if frac == 0: return low
        high = min(a[i+1 .. n-1])        # after select, everything right of i is >= a[i]
        return low + frac * (high - low)

Complexity
----------
    select:   expected O(n) time (random pivot); worst case O(n^2) if every pivot
              is the extreme value, which random choice makes vanishingly unlikely.
              O(1) extra space: partitioning swaps in place and the loop is iterative.
    quantile: O(n) expected, plus one O(n) scan for the interpolation neighbour.
    iqr_fences: two quantiles on one copy of the data -> O(n) time, O(n) space
              for the copy (we copy so the caller's list is not reordered).

Three-way partitioning matters on this dataset: fares cluster on identical
values (e.g. JFK flat fare), and a two-way partition degrades towards O(n^2)
when many keys are equal.
"""
from __future__ import annotations

import random
from typing import List, Sequence, Tuple

_rng = random.Random(2024)  # deterministic pivots -> reproducible runs


def _partition3(a: List[float], lo: int, hi: int, pivot: float) -> Tuple[int, int]:
    """Dutch-national-flag partition of a[lo..hi] around pivot.

    Returns (lt, gt) such that a[lo..lt-1] < pivot, a[lt..gt] == pivot,
    a[gt+1..hi] > pivot.
    """
    lt, i, gt = lo, lo, hi
    while i <= gt:
        v = a[i]
        if v < pivot:
            a[lt], a[i] = a[i], a[lt]
            lt += 1
            i += 1
        elif v > pivot:
            a[gt], a[i] = a[i], a[gt]
            gt -= 1
        else:
            i += 1
    return lt, gt


def select(a: List[float], k: int) -> float:
    """Return the k-th smallest element (0-based). Reorders `a` in place."""
    n = len(a)
    if not 0 <= k < n:
        raise IndexError(f"k={k} out of range for {n} values")
    lo, hi = 0, n - 1
    while lo < hi:
        pivot = a[_rng.randint(lo, hi)]
        lt, gt = _partition3(a, lo, hi, pivot)
        if k < lt:
            hi = lt - 1
        elif k > gt:
            lo = gt + 1
        else:
            return pivot
    return a[lo]


def quantile(a: List[float], q: float) -> float:
    """q-quantile with linear interpolation. Reorders `a` in place."""
    if not a:
        raise ValueError("quantile of empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    pos = q * (len(a) - 1)
    i = int(pos)
    frac = pos - i
    low = select(a, i)
    if frac == 0 or i + 1 >= len(a):
        return low
    # After select(), every element right of index i is >= a[i]; the next
    # order statistic is simply the minimum of that block.
    high = a[i + 1]
    for j in range(i + 2, len(a)):
        if a[j] < high:
            high = a[j]
    return low + frac * (high - low)


def iqr_fences(values: Sequence[float], k: float = 1.5) -> dict:
    """Tukey fences: [Q1 - k*IQR, Q3 + k*IQR]. Does not modify `values`."""
    work = list(values)
    q1 = quantile(work, 0.25)
    q3 = quantile(work, 0.75)
    iqr = q3 - q1
    return {"q1": q1, "q3": q3, "iqr": iqr, "lower": q1 - k * iqr, "upper": q3 + k * iqr}


def flag_outliers(values: Sequence[float], k: float = 1.5) -> Tuple[List[bool], dict]:
    """Return a parallel list of booleans (True = outside the fences) and the fences."""
    fences = iqr_fences(values, k)
    lower, upper = fences["lower"], fences["upper"]
    return [v < lower or v > upper for v in values], fences
