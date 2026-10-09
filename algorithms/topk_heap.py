"""Hand-built binary min-heap and a bounded top-k selector.

Problem it solves: the rankings endpoint ("busiest pickup zones", "busiest
zone-to-zone routes", "slowest zones") receives an *unordered* stream of
groups from SQL — up to 265 x 265 ≈ 70,000 origin–destination pairs — and must
return the k largest. Sorting all g groups costs O(g log g); keeping a min-heap
of size k costs O(g log k) and only O(k) memory, and works on a stream.

No heapq, sorted(), list.sort() or collections.Counter are used here.

Pseudo-code
-----------
    top_k(stream, k):
        heap = empty min-heap               # root = smallest of the current top k
        for item in stream:
            if heap.size < k: heap.push(item)
            elif item.key > heap.peek().key: heap.replace_root(item)
        result = []
        while heap not empty: result.append(heap.pop())   # ascending
        return reverse(result)                             # descending

    push: append at the end, sift up while parent > child          O(log k)
    pop / replace_root: move last to root, sift down to smaller child  O(log k)

Complexity: O(g log k) time, O(k) space, single pass over g groups.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, List, Tuple


class MinHeap:
    """Array-backed binary min-heap of (key, tiebreak, item) entries."""

    def __init__(self) -> None:
        self._a: List[Tuple[Any, Any, Any]] = []

    def __len__(self) -> int:
        return len(self._a)

    def peek(self):
        if not self._a:
            raise IndexError("peek from empty heap")
        return self._a[0]

    def push(self, entry) -> None:
        self._a.append(entry)
        self._sift_up(len(self._a) - 1)

    def pop(self):
        if not self._a:
            raise IndexError("pop from empty heap")
        last = self._a.pop()
        if not self._a:
            return last
        root, self._a[0] = self._a[0], last
        self._sift_down(0)
        return root

    def replace_root(self, entry):
        """Pop the minimum and push `entry` in one O(log n) step."""
        root, self._a[0] = self._a[0], entry
        self._sift_down(0)
        return root

    def _sift_up(self, i: int) -> None:
        a = self._a
        while i > 0:
            parent = (i - 1) // 2
            if a[i] < a[parent]:
                a[i], a[parent] = a[parent], a[i]
                i = parent
            else:
                break

    def _sift_down(self, i: int) -> None:
        a, n = self._a, len(self._a)
        while True:
            left, right, smallest = 2 * i + 1, 2 * i + 2, i
            if left < n and a[left] < a[smallest]:
                smallest = left
            if right < n and a[right] < a[smallest]:
                smallest = right
            if smallest == i:
                return
            a[i], a[smallest] = a[smallest], a[i]
            i = smallest


def top_k(items: Iterable[Any], k: int, key: Callable[[Any], Any]) -> List[Any]:
    """Return the k items with the largest key, largest first.

    Ties are broken by arrival order (earlier wins) so results are stable.
    """
    if k <= 0:
        return []
    heap = MinHeap()
    for seq, item in enumerate(items):
        # Negative sequence number: among equal keys the *later* item is
        # "smaller" and therefore evicted first.
        entry = (key(item), -seq, item)
        if len(heap) < k:
            heap.push(entry)
        elif entry > heap.peek():
            heap.replace_root(entry)
    ascending = []
    while len(heap):
        ascending.append(heap.pop()[2])
    return ascending[::-1]
