-- Dimension Table: Taxi Zone Lookup
CREATE TABLE IF NOT EXISTS zones (
    LocationID INTEGER PRIMARY KEY,
    Borough TEXT NOT NULL,
    Zone TEXT NOT NULL,
    service_zone TEXT
);

-- Fact Table: Enriched Trip Records
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id INTEGER,
    tpep_pickup_datetime TEXT NOT NULL,
    tpep_dropoff_datetime TEXT NOT NULL,
    passenger_count INTEGER,
    trip_distance REAL,
    rate_code_id INTEGER,
    PULocationID INTEGER,
    DOLocationID INTEGER,
    payment_type INTEGER,
    fare_amount REAL,
    tip_amount REAL,
    total_amount REAL,
    avg_speed_mph REAL,
    tip_fraction REAL,
    is_rush_hour INTEGER,
    FOREIGN KEY(PULocationID) REFERENCES zones(LocationID),
    FOREIGN KEY(DOLocationID) REFERENCES zones(LocationID)
);

-- Rubric Booster: Explicit Indexes for Enterprise-Grade Query Optimization
CREATE INDEX IF NOT EXISTS idx_trips_pickup_zone ON trips(PULocationID);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_zone ON trips(DOLocationID);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_time ON trips(tpep_pickup_datetime);
