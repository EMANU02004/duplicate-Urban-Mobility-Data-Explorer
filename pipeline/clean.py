"""Stage 3 — Clean / normalise: keep valid trips, but make every field consistent.

Nothing is dropped here. Missing or unknown categorical codes are mapped to the
dictionary's "Unknown" member so the trip still counts, and the mapping is logged.
"""
from __future__ import annotations

import pandas as pd

import config
from pipeline.quality_log import QualityLog

STAGE = "clean"


def _map_unknown(df, column, valid_codes, unknown_code, log, rule, detail):
    numeric = pd.to_numeric(df[column], errors="coerce")
    bad = numeric.isna() | ~numeric.isin(list(valid_codes)) | (numeric == unknown_code)
    log.record(df, bad, stage=STAGE, rule=rule, action="mapped_unknown",
               threshold=f"-> {unknown_code}", detail=detail)
    df[column] = numeric.where(~bad, unknown_code).astype("int64")


def clean(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    df = df.copy()

    # Secondary fields: TLC leaves these null together for some records
    # (usually street-hail app trips). Keep the trip, mark them as unknown.
    secondary = ["passenger_count", "ratecodeid", "congestion_surcharge", "airport_fee"]
    log.record(df, df[secondary].isna().all(axis=1), stage=STAGE, rule="missing_secondary_fields",
               action="mapped_unknown",
               detail="passenger_count, RatecodeID, congestion_surcharge, Airport_fee all null; trip kept")

    _map_unknown(df, "vendorid", set(config.VENDORS) - {config.UNKNOWN_VENDOR}, config.UNKNOWN_VENDOR,
                 log, "unknown_vendor", "VendorID null or not in data dictionary")
    _map_unknown(df, "ratecodeid", set(config.RATE_CODES) - {config.UNKNOWN_RATECODE}, config.UNKNOWN_RATECODE,
                 log, "unknown_rate_code", "RatecodeID null, 99, or not in data dictionary")
    _map_unknown(df, "payment_type", set(config.PAYMENT_TYPES) - {config.UNKNOWN_PAYMENT}, config.UNKNOWN_PAYMENT,
                 log, "unknown_payment_type", "payment_type null, 5, or not in data dictionary")

    # Passenger count is driver-entered; 0 or > 9 is not a real count.
    pc = pd.to_numeric(df["passenger_count"], errors="coerce")
    bad_pc = pc.notna() & ((pc < 1) | (pc > 9))
    log.record(df, bad_pc, stage=STAGE, rule="implausible_passenger_count", action="mapped_unknown",
               threshold="outside 1..9 -> NULL")
    df["passenger_count"] = pc.where(~bad_pc).astype("Int64")

    # Zones 264/265 have no polygon: keep in totals, leave off the map.
    unmappable = df["pulocationid"].isin(config.UNMAPPABLE_ZONE_IDS) | df["dolocationid"].isin(config.UNMAPPABLE_ZONE_IDS)
    log.record(df, unmappable, stage=STAGE, rule="unmappable_zone", action="flagged",
               threshold=f"LocationID in {config.UNMAPPABLE_ZONE_IDS}",
               detail="kept in counts, excluded from the map")

    # Consistent numeric types and rounding (cents for money, 2 dp for miles).
    money = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
             "total_amount", "congestion_surcharge", "airport_fee", "cbd_congestion_fee"]
    for col in money:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
    df["trip_distance"] = pd.to_numeric(df["trip_distance"]).round(2).clip(lower=0.01)
    df["pulocationid"] = df["pulocationid"].astype("int64")
    df["dolocationid"] = df["dolocationid"].astype("int64")
    return df
