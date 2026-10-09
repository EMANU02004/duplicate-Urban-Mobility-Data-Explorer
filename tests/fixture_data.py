"""Tiny TLC-shaped test fixture with *known* defects.

This is for automated tests only — it lets us assert that each cleaning rule
catches exactly the rows it should. The dashboard itself runs on the real TLC
month (see scripts/download_data.py); nothing here is loaded into it.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# 6 zones on a toy grid + the two TLC "unmappable" IDs.
ZONES = [
    (1, "EWR", "Newark Airport", "EWR"),
    (132, "Queens", "JFK Airport", "Airports"),
    (161, "Manhattan", "Midtown Center", "Yellow Zone"),
    (237, "Manhattan", "Upper East Side South", "Yellow Zone"),
    (181, "Brooklyn", "Park Slope", "Boro Zone"),
    (7, "Queens", "Astoria", "Boro Zone"),
    (264, "Unknown", "N/A", "N/A"),
    (265, "N/A", "Outside of NYC", "N/A"),
]

# Exact number of rows injected for each defect; tests assert these.
DEFECTS = {
    "missing_core_fields": 3,
    "out_of_period_pickup": 4,
    "non_positive_duration": 2,
    "too_short_duration": 2,
    "excessive_duration": 1,
    "non_positive_distance": 5,
    "extreme_distance": 1,
    "impossible_speed": 2,
    "negative_amount": 3,
    "zone_not_in_lookup": 1,
    "duplicate_trip": 2,
}


def _row(rng, pickup, minutes, miles, pu, do, fare=None):
    fare = round(3 + 2.5 * miles + 0.5 * minutes, 2) if fare is None else fare
    tip = round(fare * 0.2, 2)
    return {
        "VendorID": 2, "tpep_pickup_datetime": pickup,
        "tpep_dropoff_datetime": pickup + timedelta(minutes=minutes),
        "passenger_count": 1.0, "trip_distance": miles, "RatecodeID": 1.0,
        "store_and_fwd_flag": "N", "PULocationID": pu, "DOLocationID": do,
        "payment_type": 1, "fare_amount": fare, "extra": 1.0, "mta_tax": 0.5,
        "tip_amount": tip, "tolls_amount": 0.0, "improvement_surcharge": 1.0,
        "total_amount": round(fare + tip + 2.5, 2), "congestion_surcharge": 2.5,
        "Airport_fee": 0.0, "cbd_congestion_fee": 0.75 if pu == 161 else 0.0,
    }


def build_trips(n_clean: int = 400, seed: int = 1) -> pd.DataFrame:
    rng = random.Random(seed)
    start = datetime(2025, 3, 1)
    ids = [z[0] for z in ZONES[:6]]
    rows = []
    for i in range(n_clean):
        pickup = start + timedelta(minutes=rng.randint(0, 30 * 24 * 60))
        minutes = rng.randint(5, 40)
        miles = round(rng.uniform(0.5, min(8, minutes * 0.5)), 2)   # <= 30 mph
        rows.append(_row(rng, pickup, minutes, miles, rng.choice(ids), rng.choice(ids)))

    t = start + timedelta(days=3, hours=8)
    bad = []
    for _ in range(DEFECTS["missing_core_fields"]):
        r = _row(rng, t, 10, 2.0, 161, 237); r["PULocationID"] = None; bad.append(r)
    for y in (2002, 2008, 2009, 2024):
        bad.append(_row(rng, datetime(y, 1, 1, 9), 10, 2.0, 161, 237))
    for _ in range(DEFECTS["non_positive_duration"]):
        r = _row(rng, t, 10, 2.0, 161, 237); r["tpep_dropoff_datetime"] = t - timedelta(minutes=1); bad.append(r)
    for _ in range(DEFECTS["too_short_duration"]):
        r = _row(rng, t, 0, 0.1, 161, 237); r["tpep_dropoff_datetime"] = t + timedelta(seconds=20); bad.append(r)
    bad.append(_row(rng, t, 9 * 60, 5.0, 161, 237))                       # excessive duration
    for _ in range(DEFECTS["non_positive_distance"]):
        bad.append(_row(rng, t, 10, 0.0, 161, 237))
    bad.append(_row(rng, t, 120, 250.0, 161, 237))                        # extreme distance
    for _ in range(DEFECTS["impossible_speed"]):
        bad.append(_row(rng, t, 5, 30.0, 161, 132))                       # 360 mph
    for p in (4, 4, 3):
        r = _row(rng, t, 10, 2.0, 161, 237, fare=-12.0); r["payment_type"] = p
        r["total_amount"] = -15.5; bad.append(r)
    bad.append(_row(rng, t, 10, 2.0, 999, 237))                           # zone not in lookup
    dup = _row(rng, t + timedelta(hours=3), 12, 3.0, 237, 161)
    bad.extend([dup, dict(dup), dict(dup)])                               # 1 kept + 2 duplicates

    # Kept-but-mapped records
    r = _row(rng, t, 15, 3.0, 161, 264)
    for k in ("passenger_count", "RatecodeID", "congestion_surcharge", "Airport_fee"):
        r[k] = None
    bad.append(r)
    r = _row(rng, t, 15, 3.0, 237, 161); r["passenger_count"] = 0.0; r["RatecodeID"] = 99.0; bad.append(r)
    r = _row(rng, t, 15, 3.0, 237, 265); r["payment_type"] = 2; r["tip_amount"] = 0.0; bad.append(r)

    allrows = rows + bad
    rng.shuffle(allrows)
    return pd.DataFrame(allrows)


def write_fixture(folder: Path, n_clean: int = 400) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    trips = folder / "yellow_tripdata_2025-03.parquet"
    build_trips(n_clean).to_parquet(trips, index=False)
    pd.DataFrame(ZONES, columns=["LocationID", "Borough", "Zone", "service_zone"]).to_csv(
        folder / "taxi_zone_lookup.csv", index=False)
    features = []
    for i, (zid, borough, name, _) in enumerate(ZONES[:6]):
        x, y = -74.0 + 0.02 * (i % 3), 40.70 + 0.02 * (i // 3)
        ring = [[x, y], [x + 0.02, y], [x + 0.02, y + 0.02], [x, y + 0.02], [x, y]]
        features.append({"type": "Feature", "properties": {"LocationID": zid},
                         "geometry": {"type": "Polygon", "coordinates": [ring]}})
    (folder / "taxi_zones.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return trips
