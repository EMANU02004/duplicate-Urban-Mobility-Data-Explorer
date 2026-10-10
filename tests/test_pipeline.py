import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline.engine import run_etl


class PipelineTest(unittest.TestCase):
    def test_normalizes_filters_and_flags_tlc_rows(self):
        raw_trips = pd.DataFrame(
            [
                {
                    "VendorID": 1,
                    "tpep_pickup_datetime": "2024-01-02 08:00:00",
                    "tpep_dropoff_datetime": "2024-01-02 08:30:00",
                    "passenger_count": 1,
                    "trip_distance": 3.2,
                    "RatecodeID": 1,
                    "PULocationID": 1,
                    "DOLocationID": 2,
                    "payment_type": 1,
                    "fare_amount": 15.0,
                    "tip_amount": 3.0,
                    "total_amount": 20.0,
                    "extra_raw_column": "ignored",
                },
                {
                    "VendorID": 1,
                    "tpep_pickup_datetime": "2024-01-02 09:00:00",
                    "tpep_dropoff_datetime": "2024-01-02 09:45:00",
                    "passenger_count": 1,
                    "trip_distance": 0.0,
                    "RatecodeID": 1,
                    "PULocationID": 1,
                    "DOLocationID": 2,
                    "payment_type": 2,
                    "fare_amount": 60.0,
                    "tip_amount": 0.0,
                    "total_amount": 60.0,
                    "extra_raw_column": "ignored",
                },
                {
                    "VendorID": 1,
                    "tpep_pickup_datetime": "2024-01-02 10:00:00",
                    "tpep_dropoff_datetime": "2024-01-02 10:30:00",
                    "passenger_count": 1,
                    "trip_distance": 3.2,
                    "RatecodeID": 1,
                    "PULocationID": 1,
                    "DOLocationID": 2,
                    "payment_type": 1,
                    "fare_amount": 15.0,
                    "tip_amount": 3.0,
                    "total_amount": 20.0,
                    "extra_raw_column": "ignored",
                },
            ]
        )
        zones = pd.DataFrame(
            {
                "LocationID": [1, 2],
                "Borough": ["Manhattan", "Brooklyn"],
                "Zone": ["A", "B"],
                "service_zone": ["Yellow", "Boro"],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parquet_path = root / "trips.parquet"
            zones_path = root / "zones.csv"
            output_dir = root / "output"
            raw_trips.to_parquet(parquet_path)
            zones.to_csv(zones_path, index=False)
            connection = sqlite3.connect(":memory:")
            schema = Path(__file__).parents[1] / "database" / "schema.sql"
            connection.executescript(schema.read_text(encoding="utf-8"))

            run_etl(parquet_path, zones_path, connection, output_dir)

            self.assertEqual(connection.execute("SELECT COUNT(*) FROM trips").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM flagged_trips").fetchone()[0], 1)
            quality_log = (output_dir / "quality_log.txt").read_text(encoding="utf-8")
            self.assertIn("duplicates: 1", quality_log)
            self.assertIn("Flagged Zero-Distance Records: 1", quality_log)
            self.assertTrue((output_dir / "excluded_rows_sample.csv").exists())
            connection.close()


if __name__ == "__main__":
    unittest.main()
