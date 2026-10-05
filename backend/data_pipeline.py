import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "urban_mobility.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

ZONE_LOOKUP = [
    (1, "Manhattan", "East Harlem", "Yellow"),
    (2, "Manhattan", "Upper East Side", "Yellow"),
    (3, "Queens", "JFK Airport", "Airport"),
    (4, "Brooklyn", "Downtown Brooklyn", "Boro"),
    (5, "Brooklyn", "Williamsburg", "Boro"),
    (6, "Queens", "Long Island City", "Boro"),
    (7, "Bronx", "Fordham", "Boro"),
    (8, "Staten Island", "St. George", "Boro"),
    (9, "Manhattan", "Chelsea", "Yellow"),
    (10, "Manhattan", "Midtown East", "Yellow"),
    (11, "Queens", "Astoria", "Boro"),
    (12, "Brooklyn", "Crown Heights", "Boro"),
    (13, "Queens", "Flushing", "Boro"),
    (14, "Bronx", "Mott Haven", "Boro"),
    (15, "Brooklyn", "Bedford-Stuyvesant", "Boro"),
    (16, "Manhattan", "Lower East Side", "Yellow"),
    (17, "Brooklyn", "Sunset Park", "Boro"),
    (18, "Queens", "Rockaway", "Boro"),
    (19, "Brooklyn", "Park Slope", "Boro"),
    (20, "Manhattan", "Financial District", "Yellow"),
]

GEOJSON_TEMPLATE = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]
}


class TopZonesTracker:
    def __init__(self, limit=5):
        self.limit = limit
        self.entries = []

    def add(self, name, value):
        self.entries.append({"name": name, "value": value})
        if len(self.entries) > self.limit:
            self.entries = self._insertion_sort_desc(self.entries)[: self.limit]

    def report(self):
        return self._insertion_sort_desc(self.entries)

    def _insertion_sort_desc(self, items):
        ordered = list(items)
        for index in range(1, len(ordered)):
            current = ordered[index]
            cursor = index - 1
            while cursor >= 0 and ordered[cursor]["value"] < current["value"]:
                ordered[cursor + 1] = ordered[cursor]
                cursor -= 1
            ordered[cursor + 1] = current
        return ordered


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed_zone_lookup(conn):
    conn.executemany(
        "INSERT OR IGNORE INTO taxi_zone_lookup (location_id, borough, zone, service_zone) VALUES (?, ?, ?, ?)",
        ZONE_LOOKUP,
    )


def seed_zone_geometry(conn):
    for zone_id, borough, zone_name, _ in ZONE_LOOKUP:
        geometry = json.dumps({
            **GEOJSON_TEMPLATE,
            "properties": {"zone_id": zone_id, "borough": borough, "zone_name": zone_name}
        })
        conn.execute(
            "INSERT OR IGNORE INTO taxi_zones (zone_id, borough, zone_name, geometry) VALUES (?, ?, ?, ?)",
            (zone_id, borough, zone_name, geometry),
        )


def generate_demo_trips(row_count=12000):
    random.seed(42)
    start = datetime(2024, 1, 1, 0, 0)
    rows = []
    seen = set()

    for _ in range(row_count):
        pickup_zone = random.choice(ZONE_LOOKUP)
        dropoff_zone = random.choice(ZONE_LOOKUP)
        if pickup_zone[0] == dropoff_zone[0]:
            dropoff_zone = random.choice(ZONE_LOOKUP)

        pickup_dt = start + timedelta(minutes=random.randint(0, 60 * 24 * 180))
        trip_duration_minutes = max(5, int(abs(random.gauss(18, 11)) + random.randint(5, 40)))
        trip_distance = max(0.5, min(25.0, abs(random.gauss(3.2, 2.3))))
        avg_speed = round((trip_distance / (trip_duration_minutes / 60)) if trip_duration_minutes else 0.0, 2)
        fare_amount = round(max(5.0, trip_distance * 2.75 + trip_duration_minutes * 0.4 + random.uniform(0, 10)), 2)
        extra = round(random.uniform(0.0, 2.5), 2)
        mta_tax = 0.5
        tip_amount = round(random.uniform(0.0, 9.0), 2)
        tolls_amount = round(random.uniform(0.0, 4.5), 2)
        improvement_surcharge = 1.0
        total_amount = round(fare_amount + extra + mta_tax + tip_amount + tolls_amount + improvement_surcharge, 2)
        trip_category = "High Speed" if avg_speed > 18 else "Standard" if avg_speed >= 8 else "Slow Traffic"

        row = (
            random.choice(["CMT", "VTS", "DDS"]),
            pickup_dt.strftime("%Y-%m-%d %H:%M:%S"),
            (pickup_dt + timedelta(minutes=trip_duration_minutes)).strftime("%Y-%m-%d %H:%M:%S"),
            pickup_zone[0],
            dropoff_zone[0],
            random.randint(1, 6),
            round(trip_distance, 2),
            float(trip_duration_minutes),
            avg_speed,
            fare_amount,
            extra,
            mta_tax,
            tip_amount,
            tolls_amount,
            improvement_surcharge,
            total_amount,
            trip_category,
        )
        signature = (row[1], row[2], row[3], row[4], row[6], row[9])
        if signature in seen:
            continue
        seen.add(signature)
        rows.append(row)
        if len(rows) >= row_count:
            break

    return rows


def ensure_demo_data():
    conn = connect_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())

    if conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0:
        seed_zone_lookup(conn)
        seed_zone_geometry(conn)
        rows = generate_demo_trips(12000)
        conn.executemany(
            """
            INSERT INTO trips (
                vendor_id, pickup_datetime, dropoff_datetime, pickup_location_id,
                dropoff_location_id, passenger_count, trip_distance, trip_duration_minutes,
                avg_speed_mph, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
                improvement_surcharge, total_amount, trip_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    conn.close()


if __name__ == "__main__":
    ensure_demo_data()
    print(f"Demo dataset ready at {DB_PATH}")
