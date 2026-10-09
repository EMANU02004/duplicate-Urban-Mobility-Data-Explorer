"""HTTP routes. Each one: validate input -> call a query -> return JSON."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory

import config
from api import queries
from api.filters import BadRequest, Filters, metric_arg

bp = Blueprint("api", __name__)
_geojson_cache: dict = {}


def db():
    return current_app.get_db()


def filters() -> Filters:
    return Filters.from_args(request.args)


def int_arg(name, default, lo, hi) -> int:
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(f"'{name}' must be an integer")
    if not lo <= value <= hi:
        raise BadRequest(f"'{name}' must be between {lo} and {hi}")
    return value


@bp.route("/")
def index():
    return send_from_directory(config.FRONTEND_DIR, "index.html")


@bp.route("/api/health")
def health():
    ok = current_app.config["DB_PATH"].exists()
    return jsonify({"status": "ok" if ok else "no-database"}), (200 if ok else 503)


@bp.route("/api/meta")
def meta():
    return jsonify(queries.meta(db()))


@bp.route("/api/overview")
def overview():
    return jsonify(queries.overview(db(), filters()))


@bp.route("/api/hourly")
def hourly():
    return jsonify({"hourly": queries.hourly_profile(db(), filters())})


@bp.route("/api/map")
def zone_map():
    return jsonify(queries.zone_metrics(db(), filters(), metric_arg(request.args)))


@bp.route("/api/zones/geojson")
def zones_geojson():
    key = str(current_app.config["DB_PATH"])
    if key not in _geojson_cache:
        _geojson_cache[key] = queries.zones_geojson(db())
    return jsonify(_geojson_cache[key])


@bp.route("/api/zones/<int:location_id>")
def zone_detail(location_id):
    result = queries.zone_detail(db(), location_id, filters())
    if result is None:
        abort(404)
    return jsonify(result)


@bp.route("/api/heatmap")
def heatmap():
    return jsonify(queries.heatmap(db(), filters(), metric_arg(request.args)))


@bp.route("/api/distribution")
def distribution():
    column = request.args.get("metric", "avg_speed_mph")
    return jsonify(queries.distribution(db(), filters(), column, int_arg("bins", 20, 5, 60)))


@bp.route("/api/rankings")
def rankings():
    return jsonify(queries.rankings(
        db(), filters(), request.args.get("type", "zones"), request.args.get("by", "trips"),
        int_arg("k", 10, 1, 50)))


@bp.route("/api/trips")
def trips():
    return jsonify(queries.trip_list(
        db(), filters(),
        sort=request.args.get("sort", "pickup_datetime"),
        order=request.args.get("order", "desc"),
        page=int_arg("page", 1, 1, 1_000_000),
        page_size=int_arg("page_size", config.DEFAULT_PAGE_SIZE, 1, config.MAX_PAGE_SIZE)))


@bp.route("/api/trips/<int:trip_id>")
def trip_detail(trip_id):
    result = queries.trip_detail(db(), trip_id)
    if result is None:
        abort(404)
    return jsonify(result)


@bp.route("/api/data-quality")
def data_quality():
    return jsonify(queries.data_quality(db()))
