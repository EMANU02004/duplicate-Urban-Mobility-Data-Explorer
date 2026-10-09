"""Single place for paths, thresholds and settings.

Every number that affects which trips are kept or dropped lives here, so the
report can cite one file when justifying the cleaning rules.  Values can be
overridden with environment variables where noted.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Paths -----------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"            # full downloads (git-ignored)
SAMPLE_DIR = DATA_DIR / "sample"      # small committed sample for graders
OUTPUT_DIR = DATA_DIR / "output"      # exclusion log CSV, run summary
DB_PATH = Path(os.environ.get("UME_DB_PATH", DATA_DIR / "urban_mobility.db"))
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
FRONTEND_DIR = BASE_DIR / "frontend"

ZONE_LOOKUP_CSV = "taxi_zone_lookup.csv"
ZONE_SHAPES_ZIP = "taxi_zones.zip"           # official TLC shapefile bundle
ZONE_GEOJSON = "taxi_zones.geojson"          # produced from the shapefile

TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net"

# --- Story ------------------------------------------------------------------
STORY = (
    "When does New York slow down? Where and at what hours average taxi speed "
    "collapses, and what that congestion costs riders per mile."
)

# --- Cleaning thresholds (justify each one in the report) -------------------
MAX_DURATION_MIN = 6 * 60        # longer trips are almost always meters left running
MAX_DISTANCE_MI = 100            # NYC + airports + Westchester/Nassau fits well within this
MAX_SPEED_MPH = 80               # above this is not physically plausible in the city
MIN_DURATION_MIN = 1             # sub-minute "trips" are mostly cancelled/test records
UNMAPPABLE_ZONE_IDS = (264, 265) # TLC "Unknown" and "Outside of NYC"
AIRPORT_ZONE_IDS = (1, 132, 138) # EWR, JFK, LaGuardia
AIRPORT_RATECODES = (2, 3)       # JFK flat fare, Newark
OUTLIER_IQR_MULTIPLIER = 3.0     # Tukey "far out" fence: flag, don't drop
LOAD_BATCH_SIZE = 50_000

# --- Data dictionary (TLC yellow taxi dictionary, March 2025 revision) -------
VENDORS = {
    1: "Creative Mobile Technologies",
    2: "Curb Mobility",
    6: "Myle Technologies",
    7: "Helix",
    99: "Unknown",
}
RATE_CODES = {
    1: "Standard rate",
    2: "JFK",
    3: "Newark",
    4: "Nassau or Westchester",
    5: "Negotiated fare",
    6: "Group ride",
    99: "Unknown",
}
PAYMENT_TYPES = {
    0: "Flex fare",
    1: "Credit card",
    2: "Cash",
    3: "No charge",
    4: "Dispute",
    5: "Unknown",
    6: "Voided trip",
}
UNKNOWN_VENDOR = 99
UNKNOWN_RATECODE = 99
UNKNOWN_PAYMENT = 5
CARD_PAYMENT = 1

# Hour bands used for grouping without recomputing at query time.
TIME_BANDS = (
    (0, 5, "overnight"),
    (6, 9, "am_peak"),
    (10, 15, "midday"),
    (16, 19, "pm_peak"),
    (20, 23, "evening"),
)

# --- API ---------------------------------------------------------------------
API_PORT = int(os.environ.get("PORT", 5050))
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
MIN_TRIPS_FOR_ZONE_RANKING = 30  # avoid "slowest zone" being a zone with 2 trips
DISTRIBUTION_RANGES = {          # histogram x-axis ranges (values beyond are clamped)
    "avg_speed_mph": (0, 40),
    "fare_per_mile": (0, 20),
    "trip_distance": (0, 20),
    "trip_duration_min": (0, 90),
}
