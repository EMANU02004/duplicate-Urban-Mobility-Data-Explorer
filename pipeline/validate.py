"""Stage 2 — Validate: remove records that cannot be real trips.

Rules run in order on the rows that survived the previous rule, so each row is
counted against exactly one drop rule and   raw − Σ dropped = loaded   holds.
"""
from __future__ import annotations

import pandas as pd

import config
from pipeline.quality_log import QualityLog

STAGE = "validate"


def _drop(df: pd.DataFrame, mask: pd.Series, log: QualityLog, rule: str,
          threshold: str = "", detail: str = "") -> pd.DataFrame:
    log.record(df, mask, stage=STAGE, rule=rule, action="dropped", threshold=threshold, detail=detail)
    return df.loc[~mask.fillna(False).astype(bool)]


def validate(df: pd.DataFrame, month: str, valid_zone_ids: set[int], log: QualityLog) -> pd.DataFrame:
    """Apply every drop rule. `month` is 'YYYY-MM' — the file's reporting period."""
    df = df.copy()
    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")
    df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"], errors="coerce")

    # 1. Core fields every analysis depends on.
    core = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "pulocationid", "dolocationid",
            "trip_distance", "fare_amount", "total_amount"]
    df = _drop(df, df[core].isna().any(axis=1), log, "missing_core_fields",
               detail="null in one of: " + ", ".join(core))

    # 2. Pickups outside the file's month (clock errors are often years off).
    start = pd.Timestamp(f"{month}-01")
    end = start + pd.offsets.MonthBegin(1)
    out = (df["tpep_pickup_datetime"] < start) | (df["tpep_pickup_datetime"] >= end)
    years = df.loc[out, "tpep_pickup_datetime"].dt.year.value_counts().head(5)
    df = _drop(df, out, log, "out_of_period_pickup", threshold=f"[{start:%Y-%m-%d}, {end:%Y-%m-%d})",
               detail="years seen: " + ", ".join(f"{int(y)}={n}" for y, n in years.items()))

    # 3–5. Duration.
    duration = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60
    df = _drop(df, duration <= 0, log, "non_positive_duration", threshold="dropoff <= pickup")
    duration = duration.loc[df.index]
    df = _drop(df, duration < config.MIN_DURATION_MIN, log, "too_short_duration",
               threshold=f"< {config.MIN_DURATION_MIN} min")
    duration = duration.loc[df.index]
    df = _drop(df, duration > config.MAX_DURATION_MIN, log, "excessive_duration",
               threshold=f"> {config.MAX_DURATION_MIN} min")
    df["trip_duration_min"] = duration.loc[df.index]

    # 6–7. Distance.
    df = _drop(df, df["trip_distance"] <= 0, log, "non_positive_distance", threshold="<= 0 mi")
    df = _drop(df, df["trip_distance"] > config.MAX_DISTANCE_MI, log, "extreme_distance",
               threshold=f"> {config.MAX_DISTANCE_MI} mi")

    # 8. Physically impossible speed for city driving.
    speed = df["trip_distance"] / (df["trip_duration_min"] / 60)
    df = _drop(df, speed > config.MAX_SPEED_MPH, log, "impossible_speed",
               threshold=f"> {config.MAX_SPEED_MPH} mph")

    # 9. Negative money = refunds / disputes / voids — not revenue.
    negative = (df["fare_amount"] < 0) | (df["total_amount"] < 0)
    by_payment = df.loc[negative, "payment_type"].map(
        lambda p: config.PAYMENT_TYPES.get(int(p), f"code {int(p)}") if pd.notna(p) else "null"
    ).value_counts()
    df = _drop(df, negative, log, "negative_amount", threshold="fare or total < 0",
               detail="by payment type: " + ", ".join(f"{k}={v}" for k, v in by_payment.items()))

    # 10. Location IDs that are not in the official lookup (would break FKs).
    unknown_zone = ~df["pulocationid"].isin(valid_zone_ids) | ~df["dolocationid"].isin(valid_zone_ids)
    df = _drop(df, unknown_zone, log, "zone_not_in_lookup", detail="PU or DO LocationID not in taxi_zone_lookup.csv")

    # 11. Exact duplicates on the fields that identify a trip.
    key = ["vendorid", "tpep_pickup_datetime", "tpep_dropoff_datetime", "pulocationid",
           "dolocationid", "trip_distance", "total_amount"]
    df = _drop(df, df.duplicated(subset=key, keep="first"), log, "duplicate_trip",
               detail="identical on " + ", ".join(key) + "; first kept")

    return df
