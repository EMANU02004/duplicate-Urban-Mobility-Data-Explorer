"""API tests against a database built from the fixture."""
import pytest

from api import create_app
from pipeline.run import run
from tests.fixture_data import write_fixture


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    folder = tmp_path_factory.mktemp("api")
    trips = write_fixture(folder, 600)
    db = folder / "api.db"
    run(trips, folder, "2025-03", db_path=db, quiet=True, output_dir=folder)
    app = create_app(db)
    app.testing = True
    return app.test_client()


def test_health_and_meta(client):
    assert client.get("/api/health").status_code == 200
    meta = client.get("/api/meta").get_json()
    assert meta["run"]["raw_rows"] == meta["run"]["excluded_rows"] + meta["run"]["loaded_rows"]
    assert "Manhattan" in meta["boroughs"]


def test_summary_and_live_paths_agree(client):
    # Same question answered from zone_hour_stats and from trips must match.
    fast = client.get("/api/overview?borough=Manhattan").get_json()
    live = client.get("/api/overview?borough=Manhattan&min_distance=0").get_json()
    assert fast["source"] == "stats" and live["source"] == "trips"
    assert fast["totals"]["trips"] == live["totals"]["trips"]
    assert fast["totals"]["avg_speed"] == pytest.approx(live["totals"]["avg_speed"], abs=0.01)


def test_heatmap_and_map(client):
    cells = client.get("/api/heatmap?metric=avg_speed").get_json()["cells"]
    assert all(0 <= c["dow"] <= 6 and 0 <= c["hour"] <= 23 for c in cells)
    zones = client.get("/api/map?metric=trips").get_json()["zones"]
    assert sum(z["trips"] for z in zones) == client.get("/api/overview").get_json()["totals"]["trips"]
    geo = client.get("/api/zones/geojson").get_json()
    assert len(geo["features"]) == 6   # 264/265 have no shape


def test_rankings_use_heap_and_are_ordered(client):
    res = client.get("/api/rankings?type=routes&by=trips&k=5").get_json()
    counts = [r["trips"] for r in res["items"]]
    assert counts == sorted(counts, reverse=True)
    assert res["groups_scanned"] >= len(counts)


def test_trips_pagination_sort_and_detail(client):
    page1 = client.get("/api/trips?sort=total_amount&order=desc&page_size=10").get_json()
    amounts = [t["total_amount"] for t in page1["trips"]]
    assert amounts == sorted(amounts, reverse=True)
    page2 = client.get("/api/trips?sort=total_amount&order=desc&page_size=10&page=2").get_json()
    assert page2["trips"][0]["total_amount"] <= amounts[-1]
    detail = client.get(f"/api/trips/{page1['trips'][0]['trip_id']}").get_json()
    assert detail["payment"] and detail["avg_speed_mph"] > 0
    assert client.get("/api/trips/99999999").status_code == 404


def test_zone_detail(client):
    res = client.get("/api/zones/161").get_json()
    assert res["zone"]["zone_name"] == "Midtown Center"
    assert len(res["top_destinations"]) <= 5


@pytest.mark.parametrize("query", [
    "/api/trips?hour_min=30", "/api/trips?start_date=March", "/api/trips?sort=drop table",
    "/api/trips?min_distance=-1", "/api/trips?min_fare=50&max_fare=10", "/api/map?metric=nope",
    "/api/trips?days=8", "/api/trips?page_size=1000",
])
def test_invalid_parameters_return_400(client, query):
    res = client.get(query)
    assert res.status_code == 400 and "error" in res.get_json()


def test_data_quality(client):
    dq = client.get("/api/data-quality").get_json()
    assert any(e["action"] == "dropped" for e in dq["log"])


def test_date_filter_same_on_both_paths(client):
    q = "start_date=2025-03-05&end_date=2025-03-12"
    fast = client.get(f"/api/overview?{q}").get_json()
    live = client.get(f"/api/overview?{q}&min_distance=0").get_json()
    assert fast["source"] == "stats" and live["source"] == "trips"
    assert fast["totals"]["trips"] == live["totals"]["trips"] > 0
