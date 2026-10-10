import os
import pandas as pd
import numpy as np

def run_etl(parquet_path, zones_csv_path, db_conn):
    print("🚀 Starting Optimized ETL Pipeline...")
    
    # 1. Extraction & Integration
    trips = pd.read_parquet(parquet_path)
    zones = pd.read_csv(zones_csv_path)
    
    # Map dimension to fact table immediately
    zone_ids = set(zones['LocationID'])
    initial_count = len(trips)
    
    # 2. Data Cleaning & Integrity Filters (Logical Boundaries)
    cleaned = trips[
        (trips['trip_distance'] > 0) & (trips['trip_distance'] < 100) &
        (trips['fare_amount'] >= 2.50) & (trips['fare_amount'] < 500) &
        (trips['passenger_count'] > 0) & (trips['passenger_count'] <= 8) &
        (trips['PULocationID'].isin(zone_ids)) & (trips['DOLocationID'].isin(zone_ids))
    ].copy()
    
    # Standardize Temporal Data
    cleaned['tpep_pickup_datetime'] = pd.to_datetime(cleaned['tpep_pickup_datetime'])
    cleaned['tpep_dropoff_datetime'] = pd.to_datetime(cleaned['tpep_dropoff_datetime'])
    
    # Calculate duration in hours for feature calculations
    duration_hrs = (cleaned['tpep_dropoff_datetime'] - cleaned['tpep_pickup_datetime']).dt.total_seconds() / 3600.0
    cleaned = cleaned[outliers := (duration_hrs > 0.01) & (duration_hrs < 5.0)]
    duration_hrs = duration_hrs[outliers]
    
    # 3. Feature Engineering (3 Distinct Justified Metrics)
    # Feature 1: Average Speed (Detects traffic conditions/congestion layout)
    cleaned['avg_speed_mph'] = np.clip(cleaned['trip_distance'] / duration_hrs, 0, 100)
    
    # Feature 2: Tip Fraction (Measures localized driver economic yield)
    cleaned['tip_fraction'] = np.where(cleaned['fare_amount'] > 0, cleaned['tip_amount'] / cleaned['fare_amount'], 0.0)
    
    # Feature 3: Is Rush Hour (Categorical indicator flag for behavioral analysis)
    pickup_hour = cleaned['tpep_pickup_datetime'].dt.hour
    pickup_day = cleaned['tpep_pickup_datetime'].dt.weekday
    cleaned['is_rush_hour'] = ((pickup_day < 5) & ((pickup_hour.between(7,9)) | (pickup_hour.between(16,18)))).astype(int)
    
    # 4. Transparency Quality Log
    dropped_count = initial_count - len(cleaned)
    with open("data/output/quality_log.txt", "w") as log:
        log.write(f"ETL Execution Summary\n===================\n")
        log.write(f"Initial Records: {initial_count}\nDropped Outliers: {dropped_count}\n")
        log.write(f"Data Retention Rate: {(len(cleaned)/initial_count)*100:.2f}%\n")
        
    # 5. Database Multi-row Streaming Load
    cleaned.to_sql('trips', db_conn, if_exists='append', index=False)
    print(f"✅ ETL complete. Transformed and loaded {len(cleaned)} records safely.")
