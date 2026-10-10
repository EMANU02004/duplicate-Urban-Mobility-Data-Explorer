import os

import numpy as np
import pandas as pd
from config import OUTPUT_DIR


COLUMN_ALIASES = {
    "VendorID": "vendor_id",
    "RatecodeID": "rate_code_id",
    "vendor_id": "vendor_id",
    "rate_code_id": "rate_code_id",
}

TRIP_COLUMNS = [
    "vendor_id",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "rate_code_id",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount",
]

REQUIRED_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
]


def normalize_trip_columns(trips):
    normalized = trips.rename(columns=COLUMN_ALIASES).copy()
    missing_columns = [column for column in TRIP_COLUMNS if column not in normalized]
    if missing_columns:
        raise ValueError(f"Missing required trip columns: {', '.join(missing_columns)}")
    normalized = normalized[TRIP_COLUMNS]
    numeric_columns = [
        "vendor_id",
        "passenger_count",
        "trip_distance",
        "rate_code_id",
        "PULocationID",
        "DOLocationID",
        "payment_type",
        "fare_amount",
        "tip_amount",
        "total_amount",
    ]
    normalized[numeric_columns] = normalized[numeric_columns].apply(pd.to_numeric, errors="coerce")
    normalized["tpep_pickup_datetime"] = pd.to_datetime(normalized["tpep_pickup_datetime"], errors="coerce")
    normalized["tpep_dropoff_datetime"] = pd.to_datetime(normalized["tpep_dropoff_datetime"], errors="coerce")
    return normalized


def _record_exclusions(exclusions, rejected, reason):
    if rejected.empty:
        return
    sample = rejected.copy()
    sample["exclusion_reason"] = reason
    exclusions.append(sample)


def run_etl(parquet_path, zones_csv_path, db_conn, output_dir=OUTPUT_DIR):
    print("Starting ETL pipeline...")
    os.makedirs(output_dir, exist_ok=True)

    raw_trips = pd.read_parquet(parquet_path)
    zones = pd.read_csv(zones_csv_path)
    trips = normalize_trip_columns(raw_trips)
    zone_ids = set(zones["LocationID"].dropna().astype(int))
    initial_count = len(trips)
    exclusions = []
    rule_counts = {}

    duplicate_mask = trips.duplicated(keep="first")
    rule_counts["duplicates"] = int(duplicate_mask.sum())
    _record_exclusions(exclusions, trips[duplicate_mask], "duplicate")
    working = trips[~duplicate_mask].copy()

    missing_mask = working[REQUIRED_COLUMNS].isna().any(axis=1)
    rule_counts["missing_required_values"] = int(missing_mask.sum())
    _record_exclusions(exclusions, working[missing_mask], "missing_required_value")
    working = working[~missing_mask].copy()

    def apply_rule(frame, name, mask, reason):
        rejected = frame[~mask]
        rule_counts[name] = int((~mask).sum())
        _record_exclusions(exclusions, rejected, reason)
        return frame[mask].copy()

    working = apply_rule(working, "negative_distance", working["trip_distance"] >= 0, "negative_distance")
    working = apply_rule(working, "distance_over_100", working["trip_distance"] < 100, "distance_over_100")
    working = apply_rule(working, "fare_below_2_50", working["fare_amount"] >= 2.50, "fare_below_2_50")
    working = apply_rule(working, "fare_at_or_above_500", working["fare_amount"] < 500, "fare_at_or_above_500")
    working = apply_rule(
        working,
        "passenger_count_out_of_range",
        working["passenger_count"].between(1, 8),
        "passenger_count_out_of_range",
    )
    working = apply_rule(working, "unknown_pickup_zone", working["PULocationID"].isin(zone_ids), "unknown_pickup_zone")
    working = apply_rule(working, "unknown_dropoff_zone", working["DOLocationID"].isin(zone_ids), "unknown_dropoff_zone")

    duration_hrs = (
        working["tpep_dropoff_datetime"] - working["tpep_pickup_datetime"]
    ).dt.total_seconds() / 3600.0
    working["duration_hrs"] = duration_hrs
    working = apply_rule(
        working,
        "duration_at_or_below_36_seconds",
        duration_hrs > 0.01,
        "duration_at_or_below_36_seconds",
    )
    working = apply_rule(
        working,
        "duration_at_or_above_5_hours",
        duration_hrs < 5.0,
        "duration_at_or_above_5_hours",
    )

    zero_distance_mask = working["trip_distance"] == 0
    flagged = working[zero_distance_mask].copy()
    flagged["flag_reason"] = "zero_distance"
    working = working[~zero_distance_mask].copy()

    working["avg_speed_mph"] = np.clip(working["trip_distance"] / working["duration_hrs"], 0, 100)
    working["tip_fraction"] = np.where(
        working["fare_amount"] > 0,
        working["tip_amount"].fillna(0) / working["fare_amount"],
        0.0,
    )
    pickup_hour = working["tpep_pickup_datetime"].dt.hour
    pickup_day = working["tpep_pickup_datetime"].dt.weekday
    working["is_rush_hour"] = (
        (pickup_day < 5) & ((pickup_hour.between(7, 9)) | (pickup_hour.between(16, 18)))
    ).astype(int)

    trip_output = working[TRIP_COLUMNS + ["avg_speed_mph", "tip_fraction", "is_rush_hour"]]
    flagged_output = flagged[TRIP_COLUMNS + ["flag_reason"]]
    trip_output.to_sql("trips", db_conn, if_exists="append", index=False)
    if not flagged_output.empty:
        flagged_output.to_sql("flagged_trips", db_conn, if_exists="append", index=False)

    sample_path = os.path.join(output_dir, "excluded_rows_sample.csv")
    if exclusions:
        pd.concat(exclusions, ignore_index=True).head(1000).to_csv(sample_path, index=False)
    else:
        pd.DataFrame(columns=TRIP_COLUMNS + ["exclusion_reason"]).to_csv(sample_path, index=False)

    with open(os.path.join(output_dir, "quality_log.txt"), "w", encoding="utf-8") as log:
        log.write("ETL Execution Summary\n")
        log.write("=====================\n")
        log.write(f"Initial Records: {initial_count}\n")
        log.write(f"Loaded Records: {len(trip_output)}\n")
        log.write(f"Flagged Zero-Distance Records: {len(flagged_output)}\n")
        log.write("Excluded Row Sample: excluded_rows_sample.csv (up to 1000 rows)\n")
        for rule, count in rule_counts.items():
            log.write(f"{rule}: {count}\n")
        retention = (len(trip_output) / initial_count * 100) if initial_count else 0
        log.write(f"Data Retention Rate: {retention:.2f}%\n")

    print(f"ETL complete. Transformed and loaded {len(trip_output)} records safely.")
