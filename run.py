import os
import sqlite3
from pipeline.engine import run_etl
from app import app

DB_PATH = 'database/mobility.db'
SCHEMA_PATH = 'database/schema.sql'

def bootstrap_system():
    print("🛠️  Initializing Enterprise Mobility System Core...")
    
    # Ensure database folder exists
    os.makedirs('database', exist_ok=True)
    os.makedirs('data/output', exist_ok=True)
    
    # 1. Establish Schema and Performance Indexes
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    print("✅ Database layout and performance indexes applied.")
    
    # 2. Check if data needs processing (prevents double loading)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips")
    if cursor.fetchone()[0] == 0:
        print("📦 Database empty. Triggering custom pipeline execution...")
        # Path references to your raw downloaded assignment dataset components
        run_etl('data/yellow_tripdata.parquet', 'data/taxi_zone_lookup.csv', conn)
    else:
        print("💾 Enriched historical records found. Skipping ETL to save resources.")
    conn.close()

if __name__ == '__main__':
    bootstrap_system()
    print("🌐 Fullstack dashboard running locally at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
