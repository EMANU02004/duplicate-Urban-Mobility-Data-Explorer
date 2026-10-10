import os
import sqlite3
from pipeline.engine import run_etl
from app import app
from config import DB_PATH, OUTPUT_DIR, SCHEMA_PATH, TRIPS_PATH, ZONES_PATH

def bootstrap_system():
    print("Starting mobility dashboard...")

    os.makedirs(DB_PATH.parent, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    print("Database layout and performance indexes applied.")

    conn.executemany(
        "INSERT OR IGNORE INTO payment_types (payment_type, description) VALUES (?, ?)",
        [
            (1, "Credit card"),
            (2, "Cash"),
            (3, "No charge"),
            (4, "Dispute"),
            (5, "Unknown"),
        ],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO rate_codes (rate_code_id, description) VALUES (?, ?)",
        [
            (1, "Standard rate"),
            (2, "JFK"),
            (3, "Newark"),
            (4, "Nassau or Westchester"),
            (5, "Negotiated fare"),
            (6, "Group ride"),
        ],
    )
    conn.commit()
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips")
    if cursor.fetchone()[0] == 0:
        print("Database empty. Running ETL...")
        missing_files = [path for path in (TRIPS_PATH, ZONES_PATH) if not path.exists()]
        if missing_files:
            missing_names = ", ".join(path.name for path in missing_files)
            conn.close()
            raise FileNotFoundError(
                f"Missing input file(s): {missing_names}. Place them in {TRIPS_PATH.parent}."
            )
        run_etl(TRIPS_PATH, ZONES_PATH, conn, OUTPUT_DIR)
    else:
        print("Enriched historical records found. Skipping ETL to save resources.")
    conn.close()

if __name__ == '__main__':
    bootstrap_system()
    print("Dashboard running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
