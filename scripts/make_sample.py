"""Create the small committed sample from a real downloaded month.

    python scripts/make_sample.py --rows 150000

Takes a seeded random sample of RAW rows (dirty rows included, so the cleaning
rules still have something to catch) and copies the zone lookup and the
converted GeoJSON into data/sample/. Commit data/sample/ so graders can run the
project without downloading 60 MB. Run the pipeline once on data/raw first so
taxi_zones.geojson exists.
"""
import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=150_000)
    args = parser.parse_args()

    months = sorted(config.RAW_DIR.glob("yellow_tripdata_*.parquet"))
    if not months:
        sys.exit("No month in data/raw. Run scripts/download_data.py first.")
    source = months[-1]
    df = pd.read_parquet(source)
    sample = df.sample(n=min(args.rows, len(df)), random_state=42).sort_values("tpep_pickup_datetime")

    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    target = config.SAMPLE_DIR / source.name.replace(".parquet", "_sample.parquet")
    sample.to_parquet(target, index=False)
    shutil.copy(config.RAW_DIR / config.ZONE_LOOKUP_CSV, config.SAMPLE_DIR / config.ZONE_LOOKUP_CSV)
    geojson = config.RAW_DIR / config.ZONE_GEOJSON
    if geojson.exists():
        shutil.copy(geojson, config.SAMPLE_DIR / config.ZONE_GEOJSON)
    else:
        print("warning: run `python -m pipeline.run` on data/raw first to produce taxi_zones.geojson")
    print(f"Wrote {len(sample):,} raw rows to {target} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
