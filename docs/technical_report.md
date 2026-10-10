# NYC Urban Mobility Data Explorer: Technical Analysis Report

## 1. Problem Framing & Dataset Analysis
The New York City Taxi & Limousine Commission (TLC) dataset acts as a high-throughput relational tracking footprint of urban transit patterns. However, raw data introduces immense logical challenges. During ingestion, significant systemic metrics aberrations were discovered and successfully resolved via our cleaning engine protocol:
- **Negative Fares & Low Durations:** Records indicating sub-zero pricing or journeys under 36 seconds represent error transactions or administrative chargebacks. These records were systematically isolated and dropped.
- **Physical Boundary Traps:** Trip distance indexes exceeding 100 miles inside municipal shifts were filtered as anomalous sensor faults.
- **Unexpected Design Observation:** We discovered millions of records showing zero recorded trip distances but carrying high fare metrics (\$50–\$100). This indicates long-duration idling or custom out-of-borough flat rate agreements. This unique observation influenced our decision to construct our database architecture with highly optimized tracking indexes across lookup configurations.

## 2. System Architecture & Design Decisions
The application uses a clean, full-stack separation of concerns:
1. **Data Layer (PostgreSQL/SQLite):** Implements a third-normal-form (3NF) relational framework mapping specific trip payloads cleanly back to corresponding zone metadata configurations.
2. **Backend Application Server (Flask Middleware):** Manages connection contexts, processes parameter boundaries, and hosts custom non-library analytical sorting algorithms.
3. **User Facing Interface (HTML5/CSS3/Vanilla JS Engine):** Offers real-time analytical parsing panels, filtering metrics interactively without third-party visual bloat.

### Architecture Trade-Off Rationale
We chose to avoid heavy ORMs (like SQLAlchemy) and instead implemented direct, optimized raw SQL operations. This provides maximum throughput speeds, zero initialization latency overheads, and keeps the application lightweight and performant.

## 3. Algorithmic Logic & Data Structures
To fully satisfy the academic requirements of this assignment, we manually built a custom **K-Way Min-Heap** structure inside `algorithms/topk_heap.py` without importing or relying on any native Python collections or external libraries.

### Algorithmic Strategy
Instead of sorting the entire data table in memory—which takes \(O(N \log N)\) time and strains system memory—our custom min-heap structure parses the records in a single pass. It holds only the top elements at any given time. If an incoming record is larger than the root of our heap, the root is replaced and the heap shifts downward to maintain structure.

### Computational Complexity Analysis
- **Time Complexity:** \(\mathcal{O}(N \log K)\) where \(N\) represents the total rows across the dataset array, and \(K\) represents the chosen sorting subset slice. This is significantly faster than standard full-table sorting mechanisms.
- **Space Complexity:** \(\mathcal{O}(K)\), providing absolute stability by storing only the target slice in system memory at any given time.

### Algorithmic Pseudo-Code Structure
```text
CLASS CustomTopKHeap:
    FUNCTION push(element):
        IF heap.length < K THEN
            APPEND element TO heap
            PERFORM bubble_up(heap.length - 1)
        ELSE IF element.value > heap[0].value THEN
            heap[0] = element
            PERFORM sink_down(0)
```
