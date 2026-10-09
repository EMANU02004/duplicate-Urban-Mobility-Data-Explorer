"""Download one month of official TLC data into data/raw/.

    python scripts/download_data.py              # default month 2025-03
    python scripts/download_data.py --month 2025-01

Files:
  yellow_tripdata_YYYY-MM.parquet   (~60 MB, ~3–4 million trips)
  taxi_zone_lookup.csv
  taxi_zones.zip                    (shapefile; converted to GeoJSON by the pipeline)
"""
import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def fetch(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  already have {dest.name}")
        return
    print(f"  downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    tmp.rename(dest)
    print(f"  saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="2025-03", help="YYYY-MM (2025+ includes the CBD congestion fee)")
    args = parser.parse_args()
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    base = config.TLC_BASE_URL
    fetch(f"{base}/trip-data/yellow_tripdata_{args.month}.parquet",
          config.RAW_DIR / f"yellow_tripdata_{args.month}.parquet")
    fetch(f"{base}/misc/taxi_zone_lookup.csv", config.RAW_DIR / config.ZONE_LOOKUP_CSV)
    fetch(f"{base}/misc/taxi_zones.zip", config.RAW_DIR / config.ZONE_SHAPES_ZIP)
    print("Done. Next: python -m pipeline.run")


if __name__ == "__main__":
    main()
