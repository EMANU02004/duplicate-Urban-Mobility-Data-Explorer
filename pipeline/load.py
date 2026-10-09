"""Stage 5 — Load: dimensions, trips (batched, transactional), summary table, log."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd

import config
from pipeline.quality_log import QualityLog

TRIP_COLUMNS = {
    # db column           : dataframe column
    "source_row": "source_row",
    "vendor_id": "vendorid",
    "rate_code_id": "ratecodeid",
    "payment_type_id": "payment_type",
    "pickup_location_id": "pulocationid",
    "dropoff_location_id": "dolocationid",
    "pickup_datetime": "pickup_datetime_str",
    "dropoff_datetime": "dropoff_datetime_str",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "congestion_surcharge": "congestion_surcharge",
    "airport_fee": "airport_fee",
    "cbd_congestion_fee": "cbd_congestion_fee",
    "total_amount": "total_amount",
    "trip_duration_min": "trip_duration_min",
    "avg_speed_mph": "avg_speed_mph",
    "fare_per_mile": "fare_per_mile",
    "tip_pct": "tip_pct",
    "pickup_date": "pickup_date",
    "pickup_hour": "pickup_hour",
    "pickup_dow": "pickup_dow",
    "is_weekend": "is_weekend",
    "time_band": "time_band",
    "is_airport_trip": "is_airport_trip",
    "is_cross_borough": "is_cross_borough",
    "pays_cbd_fee": "pays_cbd_fee",
    "is_speed_outlier": "is_speed_outlier",
    "is_fare_outlier": "is_fare_outlier",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_dimensions(conn: sqlite3.Connection, lookup: pd.DataFrame, geometry: dict[int, dict]) -> None:
    with conn:
        boroughs = sorted(lookup["borough"].unique())
        conn.executemany("INSERT INTO boroughs (borough_id, name) VALUES (?, ?)",
                         [(i + 1, b) for i, b in enumerate(boroughs)])
        borough_id = {b: i + 1 for i, b in enumerate(boroughs)}
        conn.executemany(
            "INSERT INTO zones (location_id, borough_id, zone_name, service_zone, is_mappable) VALUES (?, ?, ?, ?, ?)",
            [
                (int(r.location_id), borough_id[r.borough], r.zone_name, r.service_zone,
                 int(int(r.location_id) not in config.UNMAPPABLE_ZONE_IDS and int(r.location_id) in geometry))
                for r in lookup.itertuples()
            ],
        )
        known = set(lookup["location_id"].astype(int))
        conn.executemany(
            "INSERT INTO zone_geometry (location_id, geometry, polygon_count, centroid_lat, centroid_lng) VALUES (?, ?, ?, ?, ?)",
            [
                (zid, json.dumps(g["geometry"]), g["polygon_count"], g["centroid"][0], g["centroid"][1])
                for zid, g in geometry.items() if zid in known
            ],
        )
        conn.executemany("INSERT INTO vendors VALUES (?, ?)", config.VENDORS.items())
        conn.executemany("INSERT INTO rate_codes VALUES (?, ?)", config.RATE_CODES.items())
        conn.executemany("INSERT INTO payment_types VALUES (?, ?)", config.PAYMENT_TYPES.items())


def start_run(conn: sqlite3.Connection, source_file: str, month: str, raw_rows: int) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_at, source_file, data_month, raw_rows) VALUES (?, ?, ?, ?)",
            (now(), source_file, month, raw_rows),
        )
    return cur.lastrowid


def load_trips(conn: sqlite3.Connection, df: pd.DataFrame, run_id: int) -> int:
    """Insert in batches; each batch is one transaction so a failure never leaves half a batch."""
    df = df.copy()
    df["pickup_datetime_str"] = df["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["dropoff_datetime_str"] = df["tpep_dropoff_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    frame = df[list(TRIP_COLUMNS.values())].astype(object)
    frame = frame.where(pd.notna(frame), None)
    columns = list(TRIP_COLUMNS) + ["run_id"]
    sql = f"INSERT INTO trips ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})"

    loaded = 0
    for start in range(0, len(frame), config.LOAD_BATCH_SIZE):
        batch = frame.iloc[start:start + config.LOAD_BATCH_SIZE]
        rows = [tuple(_py(v) for v in row) + (run_id,) for row in batch.itertuples(index=False, name=None)]
        with conn:
            conn.executemany(sql, rows)
        loaded += len(rows)
    return loaded


def _py(value):
    """numpy scalars -> plain Python so sqlite3 stores INTEGER/REAL, not BLOB."""
    return value.item() if hasattr(value, "item") else value


def build_summary(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("DELETE FROM zone_hour_stats")
        conn.execute(
            """
            INSERT INTO zone_hour_stats
            SELECT pickup_location_id, pickup_date, pickup_hour, pickup_dow,
                   COUNT(*), SUM(avg_speed_mph), SUM(fare_per_mile),
                   SUM(trip_duration_min), SUM(trip_distance), SUM(total_amount)
            FROM trips
            GROUP BY pickup_location_id, pickup_date, pickup_hour
            """
        )
        conn.execute("ANALYZE")


def finish_run(conn: sqlite3.Connection, run_id: int, log: QualityLog, loaded: int) -> None:
    with conn:
        conn.executemany(
            """INSERT INTO data_quality_log
               (run_id, stage, rule, action, rows_affected, threshold, detail, sample_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(run_id, e.stage, e.rule, e.action, e.rows_affected, e.threshold, e.detail, e.sample_ids)
             for e in log.entries],
        )
        # The CHECK constraint on pipeline_runs rejects this update if raw != excluded + loaded.
        conn.execute(
            "UPDATE pipeline_runs SET finished_at = ?, excluded_rows = ?, loaded_rows = ? WHERE run_id = ?",
            (now(), log.dropped_total, loaded, run_id),
        )
