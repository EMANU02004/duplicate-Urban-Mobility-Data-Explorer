# Urban Mobility Data Explorer Technical Report

## 1. Problem framing and dataset analysis

Urban mobility analysis is a classic data engineering challenge because real trip data is rich, noisy, and operationally messy. Taxi trip records contain pickup and dropoff timestamps, trip distance, fare values, and location identifiers, but in real-world sources they often contain missing values, invalid durations, duplicate rows, and impossible fare ranges. The goal of the project was to convert raw trip signals into a clean relational model and surface meaningful transport insights through an interactive dashboard.

The project uses a NYC TLC-inspired schema with trip records, zone lookup data, and zone metadata. A practical challenge is that real trip data is usually stored as large parquet files and can be difficult to explore directly without cleaning. We therefore built a modular pipeline that validates rows, standardizes timestamps, repairs null values, removes duplicates, and normalizes location identifiers before inserting data into SQLite.

One unexpected observation was that the strongest demand patterns did not always align with the most expensive trips. Midtown and Manhattan-heavy pickup patterns generated high demand, while some suburban or airport movements created longer distances with different fare behavior. This influenced the system design by emphasizing both demand volume and route cost, rather than using only trip count as the dominant metric.

## 2. System architecture and design decisions

The system follows a simple three-layer design: frontend, backend API, and relational storage. The frontend is a single-page dashboard built with HTML, CSS, and JavaScript. It uses asynchronous requests to the backend and renders summary cards, trend bars, and trip tables without any heavy framework.

The backend is implemented with Flask because it is lightweight, Python-friendly, and suitable for quick API delivery. It exposes endpoints for summary metrics, borough trends, and filtered trip records. The database layer is SQLite, which provides enough performance for a local exploratory dashboard while keeping the project portable and easy to run.

The relational schema keeps lookup tables separate from trip events. Taxi zone metadata is stored in `taxi_zone_lookup`, while trip facts remain in the `trips` table. This keeps the system normalized and easier to query than a single denormalized dataset. Indexes on pickup time, pickup ID, and total fare improve the speed of dashboard queries for common filtering patterns.

## 3. Algorithmic logic and data structures

A key requirement of the assignment is to manually implement at least one algorithm or data structure without relying on built-in queue or counting libraries. This project implements a custom `TopZonesTracker` in the data pipeline. Instead of using `heapq`, it stores zone entries in a list and uses an insertion-sort routine to keep the highest values ordered in descending order.

Pseudo-code:

```text
initialize empty list entries
for each zone name and value:
    append item to entries
    if length > limit:
        sort the list in descending order using insertion sort
        keep only the top limit values
return sorted list
```

The insertion sort logic compares each new item with the previous entries and shifts larger values to the left. This ensures the top zones remain ranked by trip count. The time complexity is O(n^2) in the worst case for the sort step, and space complexity is O(k) for the bounded top-k list. For a dashboard focused on a small set of active zones, this is a practical and transparent solution.

## 4. Insights and interpretation

### Insight 1: Manhattan dominates trip demand

The dashboard aggregates trip counts by pickup borough. Manhattan consistently produces the largest share of trip activity because it has dense business and tourism demand. This indicates that the city’s trip network is highly centralized around core commercial districts.

### Insight 2: Evening demand peaks late at night

The hourly demand chart highlights a strong rise in trip count after 18:00 and a second surge near 22:00. This pattern suggests commuting and evening leisure demand. In urban analytics, such patterns help planners understand congestion risk and service allocation.

### Insight 3: Long-distance trips usually carry higher fares

The filtered trip table shows that total fare increases with trip distance and duration. This is expected, but the dashboard also makes it visible that trip distance is a more reliable predictor of revenue than borough alone. For transport operators, this helps estimate how pricing and route choice interact.

## 5. Reflection and future work

The project encountered several engineering trade-offs. SQLite was chosen because it keeps the app easy to run, but a production system would benefit from PostgreSQL for large datasets and concurrent API access. Similarly, the generated demo dataset is lightweight but a full TLC parquet ingestion pipeline would better support real-world analysis at scale.

Future work should include real file ingestion for the official TLC parquet and lookup tables, expanded temporal analytics, and map-based visualizations. A more robust production version could add user-authenticated dashboards, export functions, and an ETL job scheduler. The current implementation demonstrates the full stack workflow while staying compact, understandable, and runnable in a local environment.
