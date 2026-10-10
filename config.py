from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"
DATABASE_DIR = ROOT_DIR / "database"
DB_PATH = DATABASE_DIR / "mobility.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"
TRIPS_PATH = DATA_DIR / "yellow_tripdata.parquet"
ZONES_PATH = DATA_DIR / "taxi_zone_lookup.csv"
