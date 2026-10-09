"""Index evidence for the report: query plans and timings with and without indexes.

    python scripts/explain_queries.py

Works on a temporary copy of the database, drops the trip indexes, runs the
API's real queries, re-creates the indexes, runs them again, and writes
docs/evidence/query_plans.md.
"""
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

INDEXES = {
    "idx_trips_pu_zone_time": "CREATE INDEX idx_trips_pu_zone_time ON trips(pickup_location_id, pickup_datetime)",
    "idx_trips_pickup_time": "CREATE INDEX idx_trips_pickup_time ON trips(pickup_datetime)",
    "idx_trips_distance": "CREATE INDEX idx_trips_distance ON trips(trip_distance)",
    "idx_trips_total_amount": "CREATE INDEX idx_trips_total_amount ON trips(total_amount)",
}

QUERIES = {
    "Trips from one pickup zone, newest first (zone detail / trip table)":
        "SELECT * FROM trips WHERE pickup_location_id = 161 ORDER BY pickup_datetime DESC LIMIT 15",
    "Trips in a time window (date filter)":
        "SELECT COUNT(*) FROM trips WHERE pickup_datetime BETWEEN '2025-03-10 07:00:00' AND '2025-03-10 10:00:00'",
    "Long trips (distance filter)":
        "SELECT COUNT(*), AVG(avg_speed_mph) FROM trips WHERE trip_distance >= 15",
    "Most expensive trips (sort by total)":
        "SELECT trip_id, total_amount FROM trips ORDER BY total_amount DESC LIMIT 15",
}


def measure(conn, sql):
    plan = [r[3] for r in conn.execute(f"EXPLAIN QUERY PLAN {sql}")]
    start = time.perf_counter()
    for _ in range(5):
        conn.execute(sql).fetchall()
    return plan, (time.perf_counter() - start) / 5 * 1000


def main():
    if not config.DB_PATH.exists():
        sys.exit("Run `python -m pipeline.run` first.")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "copy.db"
        shutil.copy(config.DB_PATH, db)
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
        for name in INDEXES:
            conn.execute(f"DROP INDEX IF EXISTS {name}")
        before = {title: measure(conn, sql) for title, sql in QUERIES.items()}
        for sql in INDEXES.values():
            conn.execute(sql)
        conn.execute("ANALYZE")
        after = {title: measure(conn, sql) for title, sql in QUERIES.items()}
        conn.close()

    out = [f"# Query plans before and after indexing\n\nDatabase: {rows:,} trips. "
           "Times are the mean of 5 runs on the machine that ran this script.\n"]
    for title, sql in QUERIES.items():
        (p0, t0), (p1, t1) = before[title], after[title]
        out += [f"## {title}\n", f"```sql\n{sql}\n```\n",
                "| | Plan | Time |", "|---|---|---|",
                f"| Without index | `{' / '.join(p0)}` | {t0:.1f} ms |",
                f"| With index | `{' / '.join(p1)}` | {t1:.1f} ms |",
                f"\nSpeed-up: **{t0 / max(t1, 0.001):.0f}×**\n"]
    target = config.BASE_DIR / "docs" / "evidence" / "query_plans.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
