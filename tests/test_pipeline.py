"""End-to-end pipeline test on a fixture with a known number of each defect."""
import sqlite3

import pytest

from pipeline.run import run
from tests.fixture_data import DEFECTS, write_fixture

N_CLEAN = 400


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    folder = tmp_path_factory.mktemp("fixture")
    trips = write_fixture(folder, N_CLEAN)
    db = folder / "test.db"
    summary = run(trips, folder, "2025-03", db_path=db, quiet=True, output_dir=folder)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    yield summary, conn
    conn.close()


def test_counts_reconcile(built):
    summary, conn = built
    assert summary["raw_rows"] - summary["excluded_rows"] == summary["loaded_rows"]
    assert conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == summary["loaded_rows"]
    run_row = conn.execute("SELECT * FROM pipeline_runs").fetchone()
    assert run_row["raw_rows"] == run_row["excluded_rows"] + run_row["loaded_rows"]


def test_each_drop_rule_catches_its_rows(built):
    _, conn = built
    logged = {r["rule"]: r["rows_affected"] for r in
              conn.execute("SELECT rule, rows_affected FROM data_quality_log WHERE action = 'dropped'")}
    assert logged == DEFECTS


def test_kept_rows_are_mapped_not_dropped(built):
    _, conn = built
    logged = {r["rule"]: r["rows_affected"] for r in conn.execute("SELECT rule, rows_affected FROM data_quality_log")}
    assert logged["missing_secondary_fields"] == 1
    assert logged["implausible_passenger_count"] == 1
    assert logged["unmappable_zone"] == 2
    assert logged["unknown_rate_code"] >= 2    # null + 99


def test_derived_features(built):
    _, conn = built
    bad = conn.execute("""
        SELECT COUNT(*) FROM trips
        WHERE ABS(avg_speed_mph - trip_distance / (trip_duration_min / 60.0)) > 0.05
           OR ABS(fare_per_mile - fare_amount / trip_distance) > 0.05
    """).fetchone()[0]
    assert bad == 0
    # tip_pct only for card trips
    assert conn.execute("SELECT COUNT(*) FROM trips WHERE payment_type_id != 1 AND tip_pct IS NOT NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM trips WHERE pays_cbd_fee = 1").fetchone()[0] > 0


def test_foreign_keys_hold(built):
    _, conn = built
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_summary_table_matches_trips(built):
    _, conn = built
    assert conn.execute("SELECT SUM(trip_count) FROM zone_hour_stats").fetchone()[0] == \
        conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
