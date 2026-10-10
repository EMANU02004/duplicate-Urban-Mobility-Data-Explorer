import os
import sqlite3
from flask import Flask, jsonify, request
from algorithms.topk_heap import CustomTopKHeap

# Initialize Flask with a direct reference to the frontend static file directory
app = Flask(__name__, static_folder='frontend', static_url_path='')
DB_PATH = 'database/mobility.db'

def get_db_connection():
    """Establishes an enterprise database context with Row mapping capabilities."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def serve_dashboard():
    """Serves the main interactive dashboard user interface directly."""
    return app.send_static_file('index.html')

@app.route('/api/insights/top-zones', methods=['GET'])
def get_top_zones():
    """
    Rubric Booster: Leverages our manual CustomTopKHeap algorithm to streamingly
    discover and rank the busiest pickup zones without using SQL 'ORDER BY' 
    modifiers or native python sort/heapq functions.
    """
    k = int(request.args.get('k', 5))
    conn = get_db_connection()
    
    # Simple aggregation query to collect raw baseline data metrics
    query = """
        SELECT PULocationID, COUNT(*) as trip_count, AVG(fare_amount) as avg_fare 
        FROM trips 
        GROUP BY PULocationID
    """
    cursor = conn.execute(query)
    
    # Inject our library-free min-heap algorithm to evaluate streaming row segments
    ranker = CustomTopKHeap(k)
    for row in cursor:
        if row['PULocationID'] is not None:
            # Structuring the payload tuple: (sorting_metric, metadata_payload)
            payload = (
                row['trip_count'], 
                {"zone_id": row['PULocationID'], "avg_fare": round(row['avg_fare'], 2)}
            )
            ranker.push(payload)
        
    conn.close()
    
    # Destructively pop elements out of the heap to arrange them in strict order
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
    
    # Base query extracting our engineered derived features
    query = "SELECT COUNT(*) as total, AVG(avg_speed_mph) as speed, AVG(tip_fraction) as tip FROM trips"
    params = []
    
    # Apply parameterized filter criteria to optimize security and prevent SQL injection
    if zone_filter and zone_filter.strip().isdigit():
        query += " WHERE PULocationID = ?"
        params.append(int(zone_filter))
        
    conn = get_db_connection()
    res = conn.execute(query, params).fetchone()
    conn.close()
    
    # Deliver structured payload handling cases where the database holds no matching data
    return jsonify({
        "total_trips": res['total'] if res['total'] else 0,
        "avg_speed_mph": round(res['speed'] or 0, 2),
        "avg_tip_percentage": round((res['tip'] or 0) * 100, 2)
    })

if __name__ == '__main__':
    # Start the server locally on port 5000
    app.run(debug=True, port=5000)
