"""Run the full ETL: extract -> validate -> clean -> enrich -> load.

Usage (from the project root):
    python -m pipeline.run                         # uses data/raw if present, else data/sample
    python -m pipeline.run --trips data/raw/yellow_tripdata_2025-03.parquet
    python -m pipeline.run --limit 200000          # quick run on the first N raw rows

The database is rebuilt from scratch on every run so counts always match the file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from database.db import connect, create_schema  # noqa: E402
from pipeline import clean, enrich, extract, load, validate  # noqa: E402
from pipeline.quality_log import QualityLog  # noqa: E402


def find_inputs(trips_arg: str | None) -> tuple[Path, Path]:
    """Return (trip parquet, directory holding zone lookup + shapes)."""
    if trips_arg:
        trips = Path(trips_arg)
    else:
        candidates = sorted(config.RAW_DIR.glob("yellow_tripdata_*.parquet")) or \
                     sorted(config.SAMPLE_DIR.glob("yellow_tripdata_*.parquet"))
        if not candidates:
            sys.exit("No trip file found. Run `python scripts/download_data.py` first "
                     "(or pass --trips PATH).")
        trips = candidates[-1]
    if not trips.exists():
        sys.exit(f"Trip file not found: {trips}")
    for folder in (trips.parent, config.RAW_DIR, config.SAMPLE_DIR):
        if (folder / config.ZONE_LOOKUP_CSV).exists():
            return trips, folder
    sys.exit(f"{config.ZONE_LOOKUP_CSV} not found next to the trip file, in data/raw or data/sample.")


def month_from_name(path: Path) -> str:
    match = re.search(r"(\d{4}-\d{2})", path.name)
    if not match:
        sys.exit(f"Cannot infer YYYY-MM from {path.name}; pass --month.")
    return match.group(1)


def run(trips_path: Path, zone_dir: Path, month: str, limit: int | None = None,
        db_path: Path | None = None, quiet: bool = False,
        output_dir: Path | None = None) -> dict:
    say = (lambda *a: None) if quiet else print
    t0 = time.time()
    db_path = Path(db_path or config.DB_PATH)
    if db_path.exists():
        db_path.unlink()

    # 1. Extract
    trips = extract.read_trips(trips_path, limit=limit)
    lookup = extract.read_zone_lookup(zone_dir / config.ZONE_LOOKUP_CSV)
    geometry = extract.read_zone_geometry(zone_dir)
    if geometry and not (zone_dir / config.ZONE_GEOJSON).exists():
        extract.write_geojson(geometry, lookup, zone_dir / config.ZONE_GEOJSON)
    raw_rows = len(trips)
    say(f"[extract]  {raw_rows:,} raw trips from {trips_path.name}; "
        f"{len(lookup)} zones; {len(geometry)} zone shapes")

    log = QualityLog()
    # 2. Validate
    trips = validate.validate(trips, month, set(lookup["location_id"].astype(int)), log)
    say(f"[validate] {log.dropped_total:,} rows dropped; {len(trips):,} remain")
    # 3. Clean
    trips = clean.clean(trips, log)
    # 4. Enrich
    trips = enrich.enrich(trips, lookup, log)
    say(f"[enrich]   derived features added; outliers flagged")

    # 5. Load
    conn = connect(db_path)
    create_schema(conn)
    load.load_dimensions(conn, lookup, geometry)
    run_id = load.start_run(conn, trips_path.name, month, raw_rows)
    loaded = load.load_trips(conn, trips, run_id)
    load.build_summary(conn)
    load.finish_run(conn, run_id, log, loaded)
    conn.close()

    summary = {
        "run_id": run_id, "source_file": trips_path.name, "month": month,
        "raw_rows": raw_rows, "excluded_rows": log.dropped_total, "loaded_rows": loaded,
        "seconds": round(time.time() - t0, 1),
    }
    assert raw_rows - log.dropped_total == loaded, "raw - excluded != loaded"

    output_dir = Path(output_dir or config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    log.to_frame().to_csv(output_dir / "exclusion_log.csv", index=False)
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    say(f"[load]     {loaded:,} trips loaded into {db_path} "
        f"(raw {raw_rows:,} − excluded {log.dropped_total:,} = {loaded:,}) in {summary['seconds']}s")
    if not quiet:
        print(log.to_frame()[["stage", "rule", "action", "rows_affected"]].to_string(index=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trips", help="path to yellow_tripdata_YYYY-MM.parquet")
    parser.add_argument("--month", help="YYYY-MM (default: from file name)")
    parser.add_argument("--limit", type=int, help="only read the first N raw rows")
    args = parser.parse_args()
    trips_path, zone_dir = find_inputs(args.trips)
    run(trips_path, zone_dir, args.month or month_from_name(trips_path), limit=args.limit)


if __name__ == "__main__":
    main()
