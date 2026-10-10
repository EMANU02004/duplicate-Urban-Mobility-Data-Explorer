class CustomTopKHeap:
    """
    Min-heap for finding the top K values in O(N log K) time and O(K) space.
    """
    def __init__(self, k):
        self.k = k
        self.heap = []

    def push(self, element):
        if len(self.heap) < self.k:
            self.heap.append(element)
            self._bubble_up(len(self.heap) - 1)
        elif element[0] > self.heap[0][0]:
            self.heap[0] = element
            self._sink_down(0)

    def _bubble_up(self, idx):
        parent = (idx - 1) // 2
        while idx > 0 and self.heap[idx][0] < self.heap[parent][0]:
            self.heap[idx], self.heap[parent] = self.heap[parent], self.heap[idx]
            idx = parent
            parent = (idx - 1) // 2

    def _sink_down(self, idx):
        length = len(self.heap)
        while True:
            left = 2 * idx + 1
            right = 2 * idx + 2
            smallest = idx
            
            if left < length and self.heap[left][0] < self.heap[smallest][0]:
                smallest = left
            if right < length and self.heap[right][0] < self.heap[smallest][0]:
                smallest = right
                
            if smallest == idx:
                break
            self.heap[idx], self.heap[smallest] = self.heap[smallest], self.heap[idx]
            idx = smallest

    def get_sorted_results(self):
        result = []
        copied_list = list(self.heap)
        while self.heap:
            self.heap[0], self.heap[-1] = self.heap[-1], self.heap[0]
            root = self.heap.pop()
            if self.heap:
                self._sink_down(0)
            result.append(root)
        self.heap = copied_list
        return result[::-1]
