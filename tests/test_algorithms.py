"""The hand-written algorithms must agree with trusted library answers.

Libraries (numpy, sorted) are used only here, as the oracle.
"""
import random

import numpy as np
import pytest

from algorithms.quickselect import flag_outliers, iqr_fences, quantile, select
from algorithms.topk_heap import MinHeap, top_k


@pytest.mark.parametrize("n", [1, 2, 7, 100, 5001])
def test_select_matches_sorted(n):
    rng = random.Random(n)
    data = [rng.uniform(-50, 50) for _ in range(n)]
    for k in {0, n // 2, n - 1}:
        assert select(list(data), k) == sorted(data)[k]


def test_select_with_many_duplicates():
    # Like fares: thousands of identical flat-rate values.
    data = [70.0] * 4000 + [10.0] * 3000 + [5.0, 200.0]
    random.Random(1).shuffle(data)
    assert select(list(data), 3500) == sorted(data)[3500]


@pytest.mark.parametrize("q", [0.0, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_quantile_matches_numpy(q):
    rng = random.Random(42)
    data = [rng.expovariate(0.2) for _ in range(9999)]
    assert quantile(list(data), q) == pytest.approx(float(np.quantile(data, q)))


def test_iqr_fences_known_answer():
    # 1..9: Q1 = 3, Q3 = 7, IQR = 4 -> 1.5 fences = [-3, 13]
    f = iqr_fences([5, 1, 9, 3, 7, 2, 8, 4, 6], k=1.5)
    assert (f["q1"], f["q3"], f["iqr"], f["lower"], f["upper"]) == (3, 7, 4, -3, 13)


def test_flag_outliers_does_not_mutate_and_flags_extremes():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    original = list(data)
    flags, _ = flag_outliers(data, k=1.5)
    assert data == original
    assert flags == [False] * 9 + [True]


def test_min_heap_pops_in_order():
    h = MinHeap()
    values = [5, 3, 8, 1, 9, 2, 2]
    for i, v in enumerate(values):
        h.push((v, i, None))
    assert [h.pop()[0] for _ in range(len(values))] == sorted(values)


def test_top_k_matches_sorted():
    rng = random.Random(7)
    groups = [(f"route-{i}", rng.randint(0, 10_000)) for i in range(70_000)]
    got = top_k(groups, 10, key=lambda g: g[1])
    expected = sorted(groups, key=lambda g: g[1], reverse=True)[:10]
    assert [g[1] for g in got] == [g[1] for g in expected]


def test_top_k_edge_cases():
    assert top_k([], 5, key=lambda x: x) == []
    assert top_k([3, 1, 2], 0, key=lambda x: x) == []
    assert top_k([3, 1, 2], 10, key=lambda x: x) == [3, 2, 1]
    # ties keep arrival order
    assert top_k(["a", "b", "c"], 2, key=lambda x: 1) == ["a", "b"]
