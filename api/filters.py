"""Parse and validate query-string filters into SQL WHERE clauses.

Every endpoint accepts the same filters, so the dashboard can apply one filter
bar to every panel:

  start_date, end_date   YYYY-MM-DD (inclusive)
  hour_min, hour_max     0..23 pickup hour (inclusive; hour_min > hour_max wraps midnight)
  days                   comma list of weekdays 0..6 (0 = Monday)
  borough                pickup borough name
  zone                   pickup LocationID
  min_distance, max_distance   miles
  min_fare, max_fare     total amount, USD
  payment                payment_type id
  exclude_outliers       1 = drop IQR-flagged speed/fare outliers

Trade-off (documented in the report): filters on date/hour/day/zone can be
answered from the pre-aggregated zone_hour_stats table (~200k rows) instead
of scanning trips (~3M rows). Any trip-level filter switches to live queries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BadRequest(ValueError):
    """Raised for invalid query parameters; rendered as HTTP 400."""


def _int(args, name, lo=None, hi=None) -> Optional[int]:
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be an integer, got '{raw}'")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise BadRequest(f"'{name}' must be between {lo} and {hi}")
    return value


def _float(args, name) -> Optional[float]:
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be a number, got '{raw}'")
    if value < 0:
        raise BadRequest(f"'{name}' must not be negative")
    return value


def _date(args, name) -> Optional[str]:
    raw = args.get(name)
    if raw in (None, ""):
        return None
    if not DATE_RE.match(raw):
        raise BadRequest(f"'{name}' must be YYYY-MM-DD")
    return raw


@dataclass
class Filters:
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    hour_min: Optional[int] = None
    hour_max: Optional[int] = None
    days: List[int] = field(default_factory=list)
    borough: Optional[str] = None
    zone: Optional[int] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None
    min_fare: Optional[float] = None
    max_fare: Optional[float] = None
    payment: Optional[int] = None
    exclude_outliers: bool = False

    @classmethod
    def from_args(cls, args) -> "Filters":
        days_raw = args.get("days", "")
        days = []
        if days_raw:
            for part in days_raw.split(","):
                if not part.strip().isdigit() or not 0 <= int(part) <= 6:
                    raise BadRequest("'days' must be a comma list of 0..6 (0 = Monday)")
                days.append(int(part))
        f = cls(
            start_date=_date(args, "start_date"),
            end_date=_date(args, "end_date"),
            hour_min=_int(args, "hour_min", 0, 23),
            hour_max=_int(args, "hour_max", 0, 23),
            days=days,
            borough=(args.get("borough") or None) if args.get("borough") != "all" else None,
            zone=_int(args, "zone", 1, 265),
            min_distance=_float(args, "min_distance"),
            max_distance=_float(args, "max_distance"),
            min_fare=_float(args, "min_fare"),
            max_fare=_float(args, "max_fare"),
            payment=_int(args, "payment", 0, 6),
            exclude_outliers=args.get("exclude_outliers") in ("1", "true", "yes"),
        )
        if f.start_date and f.end_date and f.start_date > f.end_date:
            raise BadRequest("'start_date' must be on or before 'end_date'")
        if f.min_distance is not None and f.max_distance is not None and f.min_distance > f.max_distance:
            raise BadRequest("'min_distance' must be <= 'max_distance'")
        if f.min_fare is not None and f.max_fare is not None and f.min_fare > f.max_fare:
            raise BadRequest("'min_fare' must be <= 'max_fare'")
        return f

    @property
    def summary_compatible(self) -> bool:
        """True when zone_hour_stats can answer the query (no trip-level filters)."""
        return all(v is None for v in (self.min_distance, self.max_distance, self.min_fare,
                                       self.max_fare, self.payment)) and not self.exclude_outliers

    def where(self, source: str) -> Tuple[str, list]:
        """WHERE clause for `source` = 'trips' (alias t) or 'stats' (alias s)."""
        if source == "trips":
            col = {"date": "t.pickup_date", "hour": "t.pickup_hour", "dow": "t.pickup_dow",
                   "zone": "t.pickup_location_id"}
        else:
            col = {"date": "s.pickup_date", "hour": "s.pickup_hour", "dow": "s.pickup_dow",
                   "zone": "s.location_id"}
        clauses, params = [], []
        # On trips, filter the indexed pickup_datetime column (idx_trips_pickup_time).
        start_suffix, end_suffix = (" 00:00:00", " 23:59:59") if source == "trips" else ("", "")
        date_col = "t.pickup_datetime" if source == "trips" else col["date"]
        if self.start_date:
            clauses.append(f"{date_col} >= ?"); params.append(self.start_date + start_suffix)
        if self.end_date:
            clauses.append(f"{date_col} <= ?"); params.append(self.end_date + end_suffix)
        if self.hour_min is not None and self.hour_max is not None and self.hour_min > self.hour_max:
            clauses.append(f"({col['hour']} >= ? OR {col['hour']} <= ?)")
            params += [self.hour_min, self.hour_max]
        else:
            if self.hour_min is not None:
                clauses.append(f"{col['hour']} >= ?"); params.append(self.hour_min)
            if self.hour_max is not None:
                clauses.append(f"{col['hour']} <= ?"); params.append(self.hour_max)
        if self.days:
            clauses.append(f"{col['dow']} IN ({','.join('?' * len(self.days))})"); params += self.days
        if self.zone is not None:
            clauses.append(f"{col['zone']} = ?"); params.append(self.zone)
        if self.borough:
            clauses.append(f"{col['zone']} IN (SELECT z.location_id FROM zones z "
                           f"JOIN boroughs b ON b.borough_id = z.borough_id WHERE b.name = ?)")
            params.append(self.borough)
        if source == "trips":
            if self.min_distance is not None:
                clauses.append("t.trip_distance >= ?"); params.append(self.min_distance)
            if self.max_distance is not None:
                clauses.append("t.trip_distance <= ?"); params.append(self.max_distance)
            if self.min_fare is not None:
                clauses.append("t.total_amount >= ?"); params.append(self.min_fare)
            if self.max_fare is not None:
                clauses.append("t.total_amount <= ?"); params.append(self.max_fare)
            if self.payment is not None:
                clauses.append("t.payment_type_id = ?"); params.append(self.payment)
            if self.exclude_outliers:
                clauses.append("t.is_speed_outlier = 0 AND t.is_fare_outlier = 0")
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


# Aggregate expressions per source, so both tables return identical shapes.
AGGREGATES = {
    "trips": {
        "trips": "COUNT(*)",
        "avg_speed": "ROUND(AVG(t.avg_speed_mph), 2)",
        "fare_per_mile": "ROUND(AVG(t.fare_per_mile), 2)",
        "avg_duration": "ROUND(AVG(t.trip_duration_min), 1)",
        "avg_distance": "ROUND(AVG(t.trip_distance), 2)",
        "avg_total": "ROUND(AVG(t.total_amount), 2)",
    },
    "stats": {
        "trips": "SUM(s.trip_count)",
        "avg_speed": "ROUND(SUM(s.sum_speed_mph) / SUM(s.trip_count), 2)",
        "fare_per_mile": "ROUND(SUM(s.sum_fare_per_mile) / SUM(s.trip_count), 2)",
        "avg_duration": "ROUND(SUM(s.sum_duration_min) / SUM(s.trip_count), 1)",
        "avg_distance": "ROUND(SUM(s.sum_distance) / SUM(s.trip_count), 2)",
        "avg_total": "ROUND(SUM(s.sum_total_amount) / SUM(s.trip_count), 2)",
    },
}
FROM = {"trips": "trips t", "stats": "zone_hour_stats s"}
ZONE_COL = {"trips": "t.pickup_location_id", "stats": "s.location_id"}
HOUR_COL = {"trips": "t.pickup_hour", "stats": "s.pickup_hour"}
DOW_COL = {"trips": "t.pickup_dow", "stats": "s.pickup_dow"}
METRICS = list(AGGREGATES["trips"])


def metric_arg(args, default="avg_speed") -> str:
    metric = args.get("metric", default)
    if metric not in METRICS:
        raise BadRequest(f"'metric' must be one of {METRICS}")
    return metric


def select_list(source: str) -> str:
    return ", ".join(f"{expr} AS {name}" for name, expr in AGGREGATES[source].items())
