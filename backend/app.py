import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from data_pipeline import TopZonesTracker, ensure_demo_data

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "urban_mobility.db"
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")


@app.after_request
def add_cors_headers(response):
    """Allow the dashboard to be opened with a local static-file server."""
    origin = request.headers.get("Origin", "")
    if origin == "null" or origin.startswith(("http://localhost:", "http://127.0.0.1:")):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return send_file(FRONTEND_DIR / "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "database": str(DB_PATH)})


@app.route("/api/overview")
def overview():
    ensure_demo_data()
    conn = get_connection()
    summary = conn.execute(
        """
        SELECT COUNT(*) AS total_trips,
               ROUND(AVG(trip_distance), 2) AS avg_distance,
               ROUND(AVG(total_amount), 2) AS avg_fare
        FROM trips
        """
    ).fetchone()

    peak_hour = conn.execute(
        """
        SELECT strftime('%H', pickup_datetime) AS hour, COUNT(*) AS trip_count
        FROM trips
        GROUP BY hour
        ORDER BY trip_count DESC
        LIMIT 1
        """
    ).fetchone()

    borough_rows = conn.execute(
        """
        SELECT pickup_lookup.borough, COUNT(*) AS trip_count, ROUND(AVG(t.total_amount), 2) AS avg_fare
        FROM trips t
        JOIN taxi_zone_lookup pickup_lookup ON pickup_lookup.location_id = t.pickup_location_id
        GROUP BY pickup_lookup.borough
        ORDER BY trip_count DESC
        """
    ).fetchall()

    top_rows = conn.execute(
        """
        SELECT pickup_lookup.zone, COUNT(*) AS trip_count
        FROM trips t
        JOIN taxi_zone_lookup pickup_lookup ON pickup_lookup.location_id = t.pickup_location_id
        GROUP BY pickup_lookup.zone
        ORDER BY trip_count DESC
        LIMIT 5
        """
    ).fetchall()

    tracker = TopZonesTracker(5)
    for row in top_rows:
        tracker.add(row["zone"], row["trip_count"])

    anomaly_count = conn.execute(
        "SELECT COUNT(*) AS total FROM trips WHERE trip_distance <= 0 OR total_amount < 0 OR trip_duration_minutes <= 0"
    ).fetchone()

    payload = {
        "total_trips": summary["total_trips"],
        "avg_distance": summary["avg_distance"],
        "avg_fare": summary["avg_fare"],
        "peak_hour": peak_hour["hour"] if peak_hour else "N/A",
        "borough_summary": [dict(row) for row in borough_rows],
        "top_zones": tracker.report(),
        "anomaly_count": anomaly_count["total"],
    }
    conn.close()
    return jsonify(payload)


@app.route("/api/insights")
def insights():
    ensure_demo_data()
    conn = get_connection()

    hourly = conn.execute(
        """
        SELECT strftime('%H', pickup_datetime) AS hour, COUNT(*) AS trip_count
        FROM trips
        GROUP BY hour
        ORDER BY CAST(hour AS INTEGER)
        """
    ).fetchall()

    borough_summary = conn.execute(
        """
        SELECT pickup_lookup.borough, COUNT(*) AS trip_count
        FROM trips t
        JOIN taxi_zone_lookup pickup_lookup ON pickup_lookup.location_id = t.pickup_location_id
        GROUP BY pickup_lookup.borough
        ORDER BY trip_count DESC
        """
    ).fetchall()

    payload = {
        "hourly": [dict(row) for row in hourly],
        "borough": [dict(row) for row in borough_summary],
    }
    conn.close()
    return jsonify(payload)


@app.route("/api/trips")
def trips():
    ensure_demo_data()
    conn = get_connection()

    borough = request.args.get("borough", "all")
    limit = min(int(request.args.get("limit", "15")), 100)
    sort_field = request.args.get("sort", "fare")
    min_distance = request.args.get("min_distance", default=None, type=float)
    max_distance = request.args.get("max_distance", default=None, type=float)

    query = """
        SELECT
            t.id,
            t.pickup_datetime,
            t.dropoff_datetime,
            pickup_lookup.borough AS pickup_borough,
            pickup_lookup.zone AS pickup_zone,
            dropoff_lookup.zone AS dropoff_zone,
            t.trip_distance,
            t.total_amount,
            t.trip_duration_minutes,
            t.avg_speed_mph
        FROM trips t
        JOIN taxi_zone_lookup pickup_lookup ON pickup_lookup.location_id = t.pickup_location_id
        JOIN taxi_zone_lookup dropoff_lookup ON dropoff_lookup.location_id = t.dropoff_location_id
        WHERE 1 = 1
    """
    params = []

    if borough != "all":
        query += " AND pickup_lookup.borough = ? "
        params.append(borough)

    if min_distance is not None:
        query += " AND t.trip_distance >= ? "
        params.append(min_distance)

    if max_distance is not None:
        query += " AND t.trip_distance <= ? "
        params.append(max_distance)

    order_map = {
        "fare": "t.total_amount DESC",
        "distance": "t.trip_distance DESC",
        "time": "t.pickup_datetime DESC",
    }
    query += " ORDER BY " + order_map.get(sort_field, "t.total_amount DESC")
    query += " LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, tuple(params)).fetchall()
    payload = {"trips": [dict(row) for row in rows]}
    conn.close()
    return jsonify(payload)


if __name__ == "__main__":
    ensure_demo_data()
    app.run(debug=True, host="0.0.0.0", port=5050)
