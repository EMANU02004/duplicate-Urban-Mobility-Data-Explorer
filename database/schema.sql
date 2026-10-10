CREATE TABLE IF NOT EXISTS zones (
    LocationID INTEGER PRIMARY KEY,
    Borough TEXT NOT NULL,
    Zone TEXT NOT NULL,
    service_zone TEXT
);

CREATE TABLE IF NOT EXISTS payment_types (
    payment_type INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_codes (
    rate_code_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

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
    FOREIGN KEY(DOLocationID) REFERENCES zones(LocationID),
    FOREIGN KEY(payment_type) REFERENCES payment_types(payment_type),
    FOREIGN KEY(rate_code_id) REFERENCES rate_codes(rate_code_id)
);

CREATE TABLE IF NOT EXISTS flagged_trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id INTEGER,
    tpep_pickup_datetime TEXT NOT NULL,
    tpep_dropoff_datetime TEXT NOT NULL,
    passenger_count INTEGER,
    trip_distance REAL NOT NULL,
    rate_code_id INTEGER,
    PULocationID INTEGER,
    DOLocationID INTEGER,
    payment_type INTEGER,
    fare_amount REAL,
    tip_amount REAL,
    total_amount REAL,
    flag_reason TEXT NOT NULL,
    FOREIGN KEY(PULocationID) REFERENCES zones(LocationID),
    FOREIGN KEY(DOLocationID) REFERENCES zones(LocationID),
    FOREIGN KEY(payment_type) REFERENCES payment_types(payment_type),
    FOREIGN KEY(rate_code_id) REFERENCES rate_codes(rate_code_id)
);

CREATE INDEX IF NOT EXISTS idx_trips_pickup_zone ON trips(PULocationID);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_zone ON trips(DOLocationID);
CREATE INDEX IF NOT EXISTS idx_trips_pickup_time ON trips(tpep_pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_trips_payment_type ON trips(payment_type);
CREATE INDEX IF NOT EXISTS idx_trips_rush_hour ON trips(is_rush_hour);
CREATE INDEX IF NOT EXISTS idx_trips_dropoff_zone ON trips(DOLocationID);
CREATE INDEX IF NOT EXISTS idx_flagged_trips_reason ON flagged_trips(flag_reason);
