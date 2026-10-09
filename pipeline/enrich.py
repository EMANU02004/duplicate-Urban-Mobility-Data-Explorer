"""Stage 4 — Enrich: derived features computed from raw columns.

Feature            Why it exists
-----------------  ----------------------------------------------------------
trip_duration_min  basis for speed and per-minute economics
avg_speed_mph      distance / duration — our congestion proxy (the story metric)
fare_per_mile      what congestion costs riders; exposes short expensive trips
                   and flat-rate airport fares
tip_pct            card trips only: TLC records cash tips as ~0, so including
                   cash would understate tipping
pickup_date/hour/dow, is_weekend, time_band
                   temporal grouping without recomputing at query time
is_airport_trip    segment flag (EWR/JFK/LGA zones or airport rate codes)
is_cross_borough   segment flag; cross-borough trips use highways and bridges
pays_cbd_fee       2025+ files only: trip paid the Manhattan CBD congestion fee
is_*_outlier       Tukey far-out fences found with our quickselect (flag, not drop)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from algorithms.quickselect import iqr_fences
from pipeline.quality_log import QualityLog

STAGE = "enrich"


def _time_band(hour: pd.Series) -> pd.Series:
    band = pd.Series("", index=hour.index, dtype="object")
    for lo, hi, name in config.TIME_BANDS:
        band[(hour >= lo) & (hour <= hi)] = name
    return band


def enrich(df: pd.DataFrame, lookup: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    df = df.copy()
    hours = df["trip_duration_min"] / 60
    df["trip_duration_min"] = df["trip_duration_min"].round(2)
    df["avg_speed_mph"] = (df["trip_distance"] / hours).round(2)
    df["fare_per_mile"] = (df["fare_amount"] / df["trip_distance"]).round(2)

    card = (df["payment_type"] == config.CARD_PAYMENT) & (df["fare_amount"] > 0)
    df["tip_pct"] = np.where(card, (df["tip_amount"] / df["fare_amount"] * 100).round(1), np.nan)

    pickup = df["tpep_pickup_datetime"]
    df["pickup_date"] = pickup.dt.strftime("%Y-%m-%d")
    df["pickup_hour"] = pickup.dt.hour.astype("int64")
    df["pickup_dow"] = pickup.dt.dayofweek.astype("int64")          # 0 = Monday
    df["is_weekend"] = (df["pickup_dow"] >= 5).astype("int64")
    df["time_band"] = _time_band(df["pickup_hour"])

    df["is_airport_trip"] = (
        df["pulocationid"].isin(config.AIRPORT_ZONE_IDS)
        | df["dolocationid"].isin(config.AIRPORT_ZONE_IDS)
        | df["ratecodeid"].isin(config.AIRPORT_RATECODES)
    ).astype("int64")

    borough_of = lookup.set_index("location_id")["borough"]
    df["is_cross_borough"] = (
        df["pulocationid"].map(borough_of) != df["dolocationid"].map(borough_of)
    ).astype("int64")

    fee = pd.to_numeric(df["cbd_congestion_fee"], errors="coerce")
    df["pays_cbd_fee"] = (fee > 0).astype("Int64").where(fee.notna())

    # Outlier flags via our own quickselect IQR (see algorithms/quickselect.py).
    k = config.OUTLIER_IQR_MULTIPLIER
    for column, flag in (("avg_speed_mph", "is_speed_outlier"), ("fare_per_mile", "is_fare_outlier")):
        if df.empty:
            df[flag] = 0
            continue
        fences = iqr_fences(df[column].tolist(), k=k)
        mask = (df[column] < fences["lower"]) | (df[column] > fences["upper"])
        df[flag] = mask.astype("int64")
        log.record(df, mask, stage=STAGE, rule=f"{column}_iqr_outlier", action="flagged",
                   threshold=f"outside [{fences['lower']:.2f}, {fences['upper']:.2f}] (Q1 − {k}×IQR, Q3 + {k}×IQR)",
                   detail=f"Q1={fences['q1']:.2f}, Q3={fences['q3']:.2f}, IQR={fences['iqr']:.2f}; kept, excluded from averages on request")
    return df
