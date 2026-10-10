import sqlite3
from flask import Flask, jsonify, request
from algorithms.topk_heap import CustomTopKHeap
from config import DB_PATH

app = Flask(__name__, static_folder='frontend', static_url_path='')

def get_db_connection():
    """Open a database connection that returns named columns."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def serve_dashboard():
    """Serves the main interactive dashboard user interface directly."""
    return app.send_static_file('index.html')

@app.route('/api/insights/top-zones', methods=['GET'])
def get_top_zones():
    """Return the busiest pickup zones using the custom top-K heap."""
    k = int(request.args.get('k', 5))
    conn = get_db_connection()
    
    query = """
        SELECT PULocationID, COUNT(*) as trip_count, AVG(fare_amount) as avg_fare 
        FROM trips 
        GROUP BY PULocationID
    """
    cursor = conn.execute(query)
    
    ranker = CustomTopKHeap(k)
    for row in cursor:
        if row['PULocationID'] is not None:
            payload = (
                row['trip_count'], 
                {"zone_id": row['PULocationID'], "avg_fare": round(row['avg_fare'], 2)}
            )
            ranker.push(payload)
        
    conn.close()
    
    formatted_data = []
    for score, meta in ranker.get_sorted_results():
        formatted_data.append({
            "zone_id": meta['zone_id'],
            "trips": score,
            "avg_fare": meta['avg_fare']
        })
        
    return jsonify(formatted_data)

@app.route('/api/trips/metrics', methods=['GET'])
def get_global_metrics():
    """
    Serves dynamic KPI analytics updates to summary cards on the frontend interface, 
    supporting real-time filtering parameters.
    """
    zone_filter = request.args.get('zoneId', None)
    
    query = "SELECT COUNT(*) as total, AVG(avg_speed_mph) as speed, AVG(tip_fraction) as tip FROM trips"
    params = []
    
    if zone_filter and zone_filter.strip().isdigit():
        query += " WHERE PULocationID = ?"
        params.append(int(zone_filter))
        
    conn = get_db_connection()
    res = conn.execute(query, params).fetchone()
    conn.close()
    
    return jsonify({
        "total_trips": res['total'] if res['total'] else 0,
        "avg_speed_mph": round(res['speed'] or 0, 2),
        "avg_tip_percentage": round((res['tip'] or 0) * 100, 2)
    })


@app.route('/api/insights/peak-hours', methods=['GET'])
def get_peak_hours():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT
            CAST(strftime('%w', tpep_pickup_datetime) AS INTEGER) AS weekday,
            CAST(strftime('%H', tpep_pickup_datetime) AS INTEGER) AS hour,
            COUNT(*) AS trips,
            ROUND(AVG(avg_speed_mph), 2) AS avg_speed_mph
        FROM trips
        GROUP BY weekday, hour
        ORDER BY trips DESC
        LIMIT 24
    """).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route('/api/insights/tips-by-payment', methods=['GET'])
def get_tips_by_payment():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT t.payment_type,
               COALESCE(p.description, 'Unknown') AS payment_description,
               COUNT(*) AS trips,
               ROUND(AVG(t.tip_fraction) * 100, 2) AS avg_tip_percentage
        FROM trips AS t
        LEFT JOIN payment_types AS p ON p.payment_type = t.payment_type
        GROUP BY t.payment_type, p.description
        ORDER BY avg_tip_percentage DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route('/api/insights/borough-flows', methods=['GET'])
def get_borough_flows():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT
            pickup.Borough AS pickup_borough,
            dropoff.Borough AS dropoff_borough,
            COUNT(*) AS trips,
            ROUND(AVG(trips.avg_speed_mph), 2) AS avg_speed_mph
        FROM trips
        JOIN zones AS pickup ON pickup.LocationID = trips.PULocationID
        JOIN zones AS dropoff ON dropoff.LocationID = trips.DOLocationID
        GROUP BY pickup.Borough, dropoff.Borough
        ORDER BY trips DESC
        LIMIT 12
    """).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
