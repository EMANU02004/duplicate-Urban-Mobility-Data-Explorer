"""Stage 1 — Extract: read the raw TLC files exactly as published.

Inputs (one month):
  * yellow_tripdata_YYYY-MM.parquet  — trip records
  * taxi_zone_lookup.csv             — LocationID -> Borough, Zone, service_zone
  * taxi_zones.zip (shapefile) or taxi_zones.geojson — zone polygons
"""
from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

import config

# Raw TLC column names vary in case between years (Airport_fee vs airport_fee),
# so everything is lower-cased on read.
REQUIRED_TRIP_COLUMNS = [
    "vendorid", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count",
    "trip_distance", "ratecodeid", "pulocationid", "dolocationid", "payment_type",
    "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
    "improvement_surcharge", "total_amount",
]
OPTIONAL_TRIP_COLUMNS = ["congestion_surcharge", "airport_fee", "cbd_congestion_fee"]


def read_trips(path: Path, limit: int | None = None) -> pd.DataFrame:
    """Read the trip parquet, normalise column names, and number raw rows.

    `source_row` is the row's position in the raw file; it is carried through
    every stage so excluded rows can be traced back (sample_ids in the log).
    """
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    missing = [c for c in REQUIRED_TRIP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing expected TLC columns: {missing}")
    for col in OPTIONAL_TRIP_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[REQUIRED_TRIP_COLUMNS + OPTIONAL_TRIP_COLUMNS]
    if limit:
        df = df.head(limit)
    df = df.reset_index(drop=True)
    df.insert(0, "source_row", df.index.astype("int64"))
    return df


def read_zone_lookup(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={"locationid": "location_id", "zone": "zone_name"})
    df["borough"] = df["borough"].fillna("Unknown").astype(str).str.strip()
    df["zone_name"] = df["zone_name"].fillna("Unknown").astype(str).str.strip()
    df["service_zone"] = df["service_zone"].fillna("Unknown").astype(str).str.strip()
    return df[["location_id", "borough", "zone_name", "service_zone"]]


# --------------------------------------------------------------------- geometry
def read_zone_geometry(zone_dir: Path) -> dict[int, dict]:
    """Return {location_id: {"geometry": GeoJSON, "polygon_count": n, "centroid": (lat, lng)}}.

    Prefers a ready GeoJSON (fast, no projection libraries needed); otherwise
    converts the official shapefile, which is in NY State Plane feet (EPSG:2263).
    """
    geojson_path = zone_dir / config.ZONE_GEOJSON
    if geojson_path.exists():
        return _from_geojson(geojson_path)
    zip_path = zone_dir / config.ZONE_SHAPES_ZIP
    if zip_path.exists():
        return _from_shapefile_zip(zip_path)
    return {}


def _from_geojson(path: Path) -> dict[int, dict]:
    collection = json.loads(path.read_text(encoding="utf-8"))
    polygons_by_zone: dict[int, list] = {}
    for feature in collection["features"]:
        props = {k.lower(): v for k, v in (feature.get("properties") or {}).items()}
        location_id = int(props.get("location_id") or props.get("locationid") or props.get("objectid"))
        geom = feature["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        polygons_by_zone.setdefault(location_id, []).extend(polys)
    return {zid: _package(polys) for zid, polys in polygons_by_zone.items()}


def _from_shapefile_zip(zip_path: Path) -> dict[int, dict]:
    import shapefile  # pyshp
    from pyproj import CRS, Transformer

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        shp = next(Path(tmp).rglob("*.shp"))
        prj = shp.with_suffix(".prj")
        source_crs = CRS.from_wkt(prj.read_text()) if prj.exists() else CRS.from_epsg(2263)
        to_wgs84 = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)

        reader = shapefile.Reader(str(shp))
        field_names = [f[0].lower() for f in reader.fields[1:]]
        polygons_by_zone: dict[int, list] = {}
        for record, shape in zip(reader.iterRecords(), reader.iterShapes()):
            props = dict(zip(field_names, record))
            location_id = int(props["locationid"])
            rings = []
            parts = list(shape.parts) + [len(shape.points)]
            for start, end in zip(parts[:-1], parts[1:]):
                xs, ys = zip(*shape.points[start:end])
                lngs, lats = to_wgs84.transform(xs, ys)
                rings.append(list(zip(lngs, lats)))
            polygons_by_zone.setdefault(location_id, []).extend(_rings_to_polygons(rings))
    return {zid: _package(polys) for zid, polys in polygons_by_zone.items()}


def _signed_area(ring) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def _rings_to_polygons(rings):
    """Shapefile convention: clockwise rings are outer shells, counter-clockwise are holes."""
    polygons = []
    for ring in rings:
        if _signed_area(ring) <= 0 or not polygons:   # clockwise -> new shell
            polygons.append([ring])
        else:
            polygons[-1].append(ring)                   # hole of previous shell
    return polygons


def _simplify(ring, tolerance=0.00008):
    """Drop vertices closer than ~8 m to the last kept one; keeps payload small."""
    kept = [ring[0]]
    for x, y in ring[1:-1]:
        px, py = kept[-1]
        if abs(x - px) > tolerance or abs(y - py) > tolerance:
            kept.append((x, y))
    kept.append(ring[-1])
    if len(kept) < 4:
        return [[round(x, 5), round(y, 5)] for x, y in ring]
    return [[round(x, 5), round(y, 5)] for x, y in kept]


def _package(polygons) -> dict:
    polygons = [[_simplify(list(map(tuple, ring))) for ring in poly] for poly in polygons]
    largest = max(polygons, key=lambda p: abs(_signed_area([tuple(pt) for pt in p[0]])))
    shell = largest[0]
    centroid = (sum(pt[1] for pt in shell) / len(shell), sum(pt[0] for pt in shell) / len(shell))
    geometry = (
        {"type": "Polygon", "coordinates": polygons[0]}
        if len(polygons) == 1
        else {"type": "MultiPolygon", "coordinates": polygons}
    )
    return {"geometry": geometry, "polygon_count": len(polygons), "centroid": centroid}


def write_geojson(geometry: dict[int, dict], lookup: pd.DataFrame, path: Path) -> None:
    """Persist converted shapes so later runs (and the sample) skip the projection step."""
    names = lookup.set_index("location_id")
    features = []
    for zid, g in sorted(geometry.items()):
        props = {"location_id": zid}
        if zid in names.index:
            props.update(zone=names.at[zid, "zone_name"], borough=names.at[zid, "borough"])
        features.append({"type": "Feature", "properties": props, "geometry": g["geometry"]})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
