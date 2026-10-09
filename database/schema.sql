-- Urban Mobility Data Explorer — normalized SQLite schema
-- Star-style layout: small dimension tables + one trips fact table,
-- a pre-aggregated summary table for fast dashboard loads,
-- and a data-quality log for transparency.
-- Foreign keys are enforced per connection with: PRAGMA foreign_keys = ON;

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- dimensions
CREATE TABLE IF NOT EXISTS boroughs (
    borough_id   INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS zones (
    location_id  INTEGER PRIMARY KEY,               -- real TLC LocationID (1..265)
    borough_id   INTEGER NOT NULL REFERENCES boroughs(borough_id),
    zone_name    TEXT NOT NULL,
    service_zone TEXT,
    is_mappable  INTEGER NOT NULL DEFAULT 1 CHECK (is_mappable IN (0, 1))
);

-- One row per zone; zones with several shapes in the TLC shapefile
-- (e.g. islands) are merged into a single GeoJSON MultiPolygon.
CREATE TABLE IF NOT EXISTS zone_geometry (
    location_id  INTEGER PRIMARY KEY REFERENCES zones(location_id),
    geometry     TEXT NOT NULL,                     -- GeoJSON geometry, WGS84
    polygon_count INTEGER NOT NULL CHECK (polygon_count >= 1),
    centroid_lat REAL,
    centroid_lng REAL
);

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id    INTEGER PRIMARY KEY,
    description  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_codes (
    rate_code_id INTEGER PRIMARY KEY,
    description  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_types (
    payment_type_id INTEGER PRIMARY KEY,
    description     TEXT NOT NULL
);

-- ---------------------------------------------------------------- pipeline runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    source_file    TEXT NOT NULL,
    data_month     TEXT NOT NULL,                   -- YYYY-MM
    raw_rows       INTEGER NOT NULL CHECK (raw_rows >= 0),
    excluded_rows  INTEGER CHECK (excluded_rows >= 0),
    loaded_rows    INTEGER CHECK (loaded_rows >= 0),
    -- raw - excluded = loaded is the integrity promise of the pipeline
    CHECK (excluded_rows IS NULL OR loaded_rows IS NULL OR raw_rows = excluded_rows + loaded_rows)
);

CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL REFERENCES pipeline_runs(run_id),
    stage          TEXT NOT NULL,                   -- validate | clean | enrich
    rule           TEXT NOT NULL,
    action         TEXT NOT NULL CHECK (action IN ('dropped', 'flagged', 'mapped_unknown')),
    rows_affected  INTEGER NOT NULL CHECK (rows_affected >= 0),
    threshold      TEXT,
    detail         TEXT,
    sample_ids     TEXT                             -- comma-separated raw row numbers
);

-- ---------------------------------------------------------------- fact table
CREATE TABLE IF NOT EXISTS trips (
    trip_id               INTEGER PRIMARY KEY,
    source_row            INTEGER NOT NULL,         -- row number in the raw parquet
    run_id                INTEGER NOT NULL REFERENCES pipeline_runs(run_id),
    vendor_id             INTEGER NOT NULL REFERENCES vendors(vendor_id),
    rate_code_id          INTEGER NOT NULL REFERENCES rate_codes(rate_code_id),
    payment_type_id       INTEGER NOT NULL REFERENCES payment_types(payment_type_id),
    pickup_location_id    INTEGER NOT NULL REFERENCES zones(location_id),
    dropoff_location_id   INTEGER NOT NULL REFERENCES zones(location_id),

    pickup_datetime       TEXT NOT NULL,            -- 'YYYY-MM-DD HH:MM:SS'
    dropoff_datetime      TEXT NOT NULL,
    passenger_count       INTEGER CHECK (passenger_count IS NULL OR passenger_count BETWEEN 1 AND 9),
    trip_distance         REAL NOT NULL CHECK (trip_distance > 0),

    fare_amount           REAL NOT NULL CHECK (fare_amount >= 0),
    extra                 REAL,
    mta_tax               REAL,
    tip_amount            REAL,
    tolls_amount          REAL,
    improvement_surcharge REAL,
    congestion_surcharge  REAL,
    airport_fee           REAL,
    cbd_congestion_fee    REAL,
    total_amount          REAL NOT NULL CHECK (total_amount >= 0),

    -- derived features (computed in pipeline/enrich.py)
    trip_duration_min     REAL NOT NULL CHECK (trip_duration_min > 0),
    avg_speed_mph         REAL NOT NULL CHECK (avg_speed_mph >= 0),
    fare_per_mile         REAL NOT NULL CHECK (fare_per_mile >= 0),
    tip_pct               REAL,                     -- card trips only; NULL otherwise
    pickup_date           TEXT NOT NULL,            -- 'YYYY-MM-DD'
    pickup_hour           INTEGER NOT NULL CHECK (pickup_hour BETWEEN 0 AND 23),
    pickup_dow            INTEGER NOT NULL CHECK (pickup_dow BETWEEN 0 AND 6),  -- 0 = Monday
    is_weekend            INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    time_band             TEXT NOT NULL,
    is_airport_trip       INTEGER NOT NULL CHECK (is_airport_trip IN (0, 1)),
    is_cross_borough      INTEGER NOT NULL CHECK (is_cross_borough IN (0, 1)),
    pays_cbd_fee          INTEGER CHECK (pays_cbd_fee IS NULL OR pays_cbd_fee IN (0, 1)),
    is_speed_outlier      INTEGER NOT NULL DEFAULT 0 CHECK (is_speed_outlier IN (0, 1)),
    is_fare_outlier       INTEGER NOT NULL DEFAULT 0 CHECK (is_fare_outlier IN (0, 1)),

    CHECK (dropoff_datetime > pickup_datetime)
);

-- Indexes chosen from the API's actual WHERE / GROUP BY / ORDER BY clauses
-- (see scripts/explain_queries.py for before/after query plans).
CREATE INDEX IF NOT EXISTS idx_trips_pickup_time      ON trips(pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_trips_pu_zone_time     ON trips(pickup_location_id, pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_trips_do_zone          ON trips(dropoff_location_id);
CREATE INDEX IF NOT EXISTS idx_trips_dow_hour         ON trips(pickup_dow, pickup_hour);
CREATE INDEX IF NOT EXISTS idx_trips_distance         ON trips(trip_distance);
CREATE INDEX IF NOT EXISTS idx_trips_total_amount     ON trips(total_amount);
CREATE INDEX IF NOT EXISTS idx_trips_payment          ON trips(payment_type_id);
CREATE INDEX IF NOT EXISTS idx_zones_borough          ON zones(borough_id);
CREATE INDEX IF NOT EXISTS idx_dq_run                 ON data_quality_log(run_id);

-- ---------------------------------------------------------------- summary table
-- Pre-aggregated per pickup zone × date × hour. Sums (not averages) are stored
-- so any roll-up re-weights correctly: avg = SUM(sum_x) / SUM(trip_count).
CREATE TABLE IF NOT EXISTS zone_hour_stats (
    location_id        INTEGER NOT NULL REFERENCES zones(location_id),
    pickup_date        TEXT NOT NULL,
    pickup_hour        INTEGER NOT NULL CHECK (pickup_hour BETWEEN 0 AND 23),
    pickup_dow         INTEGER NOT NULL CHECK (pickup_dow BETWEEN 0 AND 6),
    trip_count         INTEGER NOT NULL CHECK (trip_count > 0),
    sum_speed_mph      REAL NOT NULL,
    sum_fare_per_mile  REAL NOT NULL,
    sum_duration_min   REAL NOT NULL,
    sum_distance       REAL NOT NULL,
    sum_total_amount   REAL NOT NULL,
    PRIMARY KEY (location_id, pickup_date, pickup_hour)
);
CREATE INDEX IF NOT EXISTS idx_zhs_dow_hour ON zone_hour_stats(pickup_dow, pickup_hour);
CREATE INDEX IF NOT EXISTS idx_zhs_date     ON zone_hour_stats(pickup_date);
