"""SQL for every endpoint. Routes stay thin; all data access lives here."""
from __future__ import annotations

import json
import sqlite3

import config
from algorithms.topk_heap import top_k
from api.filters import (AGGREGATES, DOW_COL, FROM, HOUR_COL, ZONE_COL, BadRequest, Filters,
                         select_list)

TRIP_SORTS = {
    "pickup_datetime": "t.pickup_datetime",
    "trip_distance": "t.trip_distance",
    "total_amount": "t.total_amount",
    "avg_speed_mph": "t.avg_speed_mph",
    "fare_per_mile": "t.fare_per_mile",
    "trip_duration_min": "t.trip_duration_min",
}


def _source(f: Filters) -> str:
    return "stats" if f.summary_compatible else "trips"


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ------------------------------------------------------------------ meta
def meta(conn: sqlite3.Connection) -> dict:
    run = conn.execute("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    span = conn.execute("SELECT MIN(pickup_date) AS first, MAX(pickup_date) AS last FROM zone_hour_stats").fetchone()
    return {
        "story": config.STORY,
        "run": dict(run) if run else None,
        "date_range": dict(span),
        "boroughs": [r["name"] for r in conn.execute(
            "SELECT name FROM boroughs WHERE name NOT IN ('Unknown', 'N/A') ORDER BY name")],
        "zones": rows(conn.execute(
            """SELECT z.location_id, z.zone_name, b.name AS borough, z.is_mappable
               FROM zones z JOIN boroughs b ON b.borough_id = z.borough_id ORDER BY z.zone_name""")),
        "payment_types": rows(conn.execute("SELECT payment_type_id AS id, description FROM payment_types")),
        "has_cbd_fee": conn.execute("SELECT 1 FROM trips WHERE pays_cbd_fee IS NOT NULL LIMIT 1").fetchone() is not None,
    }


# ------------------------------------------------------------------ overview
def overview(conn, f: Filters) -> dict:
    src = _source(f)
    where, params = f.where(src)
    totals = dict(conn.execute(f"SELECT {select_list(src)} FROM {FROM[src]} {where}", params).fetchone())
    hourly = hourly_profile(conn, f)
    busy = [h for h in hourly if h["trips"] and h["trips"] >= max(1, totals["trips"] or 0) * 0.01]
    slowest = min(busy, key=lambda h: h["avg_speed"], default=None)
    fastest = max(busy, key=lambda h: h["avg_speed"], default=None)
    return {"source": src, "totals": totals, "slowest_hour": slowest, "fastest_hour": fastest}


def hourly_profile(conn, f: Filters) -> list[dict]:
    src = _source(f)
    where, params = f.where(src)
    return rows(conn.execute(
        f"SELECT {HOUR_COL[src]} AS hour, {select_list(src)} FROM {FROM[src]} {where} "
        f"GROUP BY {HOUR_COL[src]} ORDER BY {HOUR_COL[src]}", params))


# ------------------------------------------------------------------ map + geometry
def zone_metrics(conn, f: Filters, metric: str) -> dict:
    src = _source(f)
    where, params = f.where(src)
    data = rows(conn.execute(
        f"SELECT {ZONE_COL[src]} AS location_id, {AGGREGATES[src]['trips']} AS trips, "
        f"{AGGREGATES[src][metric]} AS value FROM {FROM[src]} {where} GROUP BY {ZONE_COL[src]}", params))
    return {"source": src, "metric": metric, "zones": data}


def zones_geojson(conn) -> dict:
    features = []
    for r in conn.execute(
        """SELECT g.location_id, g.geometry, z.zone_name, b.name AS borough
           FROM zone_geometry g JOIN zones z ON z.location_id = g.location_id
           JOIN boroughs b ON b.borough_id = z.borough_id WHERE z.is_mappable = 1"""):
        features.append({
            "type": "Feature",
            "properties": {"location_id": r["location_id"], "zone": r["zone_name"], "borough": r["borough"]},
            "geometry": json.loads(r["geometry"]),
        })
    return {"type": "FeatureCollection", "features": features}


def zone_detail(conn, location_id: int, f: Filters) -> dict | None:
    info = conn.execute(
        """SELECT z.location_id, z.zone_name, z.service_zone, z.is_mappable, b.name AS borough
           FROM zones z JOIN boroughs b ON b.borough_id = z.borough_id WHERE z.location_id = ?""",
        (location_id,)).fetchone()
    if not info:
        return None
    zf = Filters(**{**f.__dict__, "zone": location_id, "borough": None})
    src = _source(zf)
    where, params = zf.where(src)
    totals = dict(conn.execute(f"SELECT {select_list(src)} FROM {FROM[src]} {where}", params).fetchone())
    # Destinations: unordered GROUP BY, our heap picks the top 5.
    twhere, tparams = zf.where("trips")
    groups = conn.execute(
        f"""SELECT t.dropoff_location_id AS location_id, COUNT(*) AS trips,
                   ROUND(AVG(t.avg_speed_mph), 2) AS avg_speed
            FROM trips t {twhere} GROUP BY t.dropoff_location_id""", tparams)
    top = top_k((dict(r) for r in groups), 5, key=lambda r: r["trips"])
    names = _zone_names(conn, [r["location_id"] for r in top])
    for r in top:
        r["zone"] = names.get(r["location_id"])
    return {"zone": dict(info), "totals": totals, "hourly": hourly_profile(conn, zf), "top_destinations": top}


def _zone_names(conn, ids) -> dict:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["location_id"]: r["zone_name"] for r in
            conn.execute(f"SELECT location_id, zone_name FROM zones WHERE location_id IN ({marks})", list(ids))}


# ------------------------------------------------------------------ heatmap
def heatmap(conn, f: Filters, metric: str) -> dict:
    src = _source(f)
    where, params = f.where(src)
    cells = rows(conn.execute(
        f"SELECT {DOW_COL[src]} AS dow, {HOUR_COL[src]} AS hour, {AGGREGATES[src]['trips']} AS trips, "
        f"{AGGREGATES[src][metric]} AS value FROM {FROM[src]} {where} "
        f"GROUP BY {DOW_COL[src]}, {HOUR_COL[src]}", params))
    return {"source": src, "metric": metric, "cells": cells}


# ------------------------------------------------------------------ distribution
def distribution(conn, f: Filters, column: str, bins: int) -> dict:
    if column not in config.DISTRIBUTION_RANGES:
        raise BadRequest(f"'metric' must be one of {list(config.DISTRIBUTION_RANGES)}")
    lo, hi = config.DISTRIBUTION_RANGES[column]
    width = (hi - lo) / bins
    where, params = f.where("trips")
    # Values outside the range are clamped into the first/last bin.
    data = conn.execute(
        f"""SELECT MIN(MAX(CAST((t.{column} - ?) / ? AS INTEGER), 0), ?) AS bin, COUNT(*) AS trips
            FROM trips t {where} GROUP BY bin""", [lo, width, bins - 1] + params).fetchall()
    counts = {r["bin"]: r["trips"] for r in data}
    return {
        "metric": column, "range": [lo, hi], "bin_width": width,
        "bins": [{"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2),
                  "trips": counts.get(i, 0)} for i in range(bins)],
    }


# ------------------------------------------------------------------ rankings (custom heap)
RANK_KEYS = {
    "trips": lambda r: r["trips"],
    "slowest": lambda r: -r["avg_speed"],
    "fastest": lambda r: r["avg_speed"],
    "fare_per_mile": lambda r: r["fare_per_mile"],
}


def rankings(conn, f: Filters, kind: str, by: str, k: int) -> dict:
    """SQL groups without ORDER BY/LIMIT; the hand-written min-heap selects the top k."""
    if by not in RANK_KEYS:
        raise BadRequest(f"'by' must be one of {list(RANK_KEYS)}")
    min_trips = config.MIN_TRIPS_FOR_ZONE_RANKING if by != "trips" else 1
    if kind == "zones":
        src = _source(f)
        where, params = f.where(src)
        a = AGGREGATES[src]
        sql = (f"SELECT {ZONE_COL[src]} AS pickup_id, {a['trips']} AS trips, {a['avg_speed']} AS avg_speed, "
               f"{a['fare_per_mile']} AS fare_per_mile FROM {FROM[src]} {where} "
               f"GROUP BY {ZONE_COL[src]} HAVING {a['trips']} >= ?")
    elif kind == "routes":
        src = "trips"
        where, params = f.where(src)
        sql = (f"SELECT t.pickup_location_id AS pickup_id, t.dropoff_location_id AS dropoff_id, COUNT(*) AS trips, "
               f"ROUND(AVG(t.avg_speed_mph), 2) AS avg_speed, ROUND(AVG(t.fare_per_mile), 2) AS fare_per_mile "
               f"FROM trips t {where} GROUP BY t.pickup_location_id, t.dropoff_location_id HAVING COUNT(*) >= ?")
    else:
        raise BadRequest("'type' must be 'zones' or 'routes'")
    cur = conn.execute(sql, params + [min_trips])
    groups_seen = 0

    def stream():
        nonlocal groups_seen
        for r in cur:
            groups_seen += 1
            yield dict(r)

    top = top_k(stream(), k, key=RANK_KEYS[by])
    ids = {r["pickup_id"] for r in top} | {r.get("dropoff_id") for r in top if r.get("dropoff_id")}
    names = _zone_names(conn, ids)
    for r in top:
        r["pickup_zone"] = names.get(r["pickup_id"])
        if "dropoff_id" in r:
            r["dropoff_zone"] = names.get(r["dropoff_id"])
    return {"type": kind, "by": by, "k": k, "groups_scanned": groups_seen,
            "min_trips": min_trips, "source": src, "items": top}


# ------------------------------------------------------------------ trips
TRIP_LIST_SELECT = """
    SELECT t.trip_id, t.pickup_datetime, t.dropoff_datetime,
           pz.zone_name AS pickup_zone, pb.name AS pickup_borough,
           dz.zone_name AS dropoff_zone, db.name AS dropoff_borough,
           t.trip_distance, t.trip_duration_min, t.avg_speed_mph, t.fare_per_mile, t.total_amount,
           p.description AS payment
    FROM trips t
    JOIN zones pz ON pz.location_id = t.pickup_location_id
    JOIN boroughs pb ON pb.borough_id = pz.borough_id
    JOIN zones dz ON dz.location_id = t.dropoff_location_id
    JOIN boroughs db ON db.borough_id = dz.borough_id
    JOIN payment_types p ON p.payment_type_id = t.payment_type_id
"""


def trip_list(conn, f: Filters, sort: str, order: str, page: int, page_size: int) -> dict:
    if sort not in TRIP_SORTS:
        raise BadRequest(f"'sort' must be one of {list(TRIP_SORTS)}")
    if order not in ("asc", "desc"):
        raise BadRequest("'order' must be 'asc' or 'desc'")
    where, params = f.where("trips")
    total = conn.execute(f"SELECT COUNT(*) FROM trips t {where}", params).fetchone()[0]
    data = rows(conn.execute(
        f"{TRIP_LIST_SELECT} {where} ORDER BY {TRIP_SORTS[sort]} {order.upper()}, t.trip_id LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size]))
    return {"total": total, "page": page, "page_size": page_size,
            "pages": max(1, -(-total // page_size)), "trips": data}


def trip_detail(conn, trip_id: int) -> dict | None:
    r = conn.execute(
        """SELECT t.*, pz.zone_name AS pickup_zone, pb.name AS pickup_borough,
                  dz.zone_name AS dropoff_zone, db.name AS dropoff_borough,
                  v.description AS vendor, rc.description AS rate_code, p.description AS payment
           FROM trips t
           JOIN zones pz ON pz.location_id = t.pickup_location_id
           JOIN boroughs pb ON pb.borough_id = pz.borough_id
           JOIN zones dz ON dz.location_id = t.dropoff_location_id
           JOIN boroughs db ON db.borough_id = dz.borough_id
           JOIN vendors v ON v.vendor_id = t.vendor_id
           JOIN rate_codes rc ON rc.rate_code_id = t.rate_code_id
           JOIN payment_types p ON p.payment_type_id = t.payment_type_id
           WHERE t.trip_id = ?""", (trip_id,)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------------------ data quality
def data_quality(conn) -> dict:
    run = conn.execute("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1").fetchone()
    if not run:
        return {"run": None, "log": []}
    log = rows(conn.execute(
        "SELECT stage, rule, action, rows_affected, threshold, detail, sample_ids "
        "FROM data_quality_log WHERE run_id = ? ORDER BY log_id", (run["run_id"],)))
    return {"run": dict(run), "log": log}
