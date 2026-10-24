"""Constants for Metlink Explorer v2."""

DOMAIN = "metlink_explorer"

CONF_METLINK_KEY = "metlink_api_key"
CONF_AIS_KEY = "aisstream_api_key"
METLINK_BASE_URL = "https://api.opendata.metlink.org.nz/v1"
FRONTEND_URL_BASE = "/metlink_explorer_frontend"

STATIC_GTFS_URL = "https://static.opendata.metlink.org.nz/v1/gtfs/full.zip"
STATIC_CHECK_INTERVAL_HOURS = 24
STATIC_DB_FILENAME = "metlink_explorer_gtfs.db"
STATIC_DB_SCHEMA_VERSION = 2

# GTFS route_type -> mode. School buses are bus mode with the is_school flag.
ROUTE_TYPE_MODES = {
    2: "train",
    3: "bus",
    4: "ferry",
    5: "cable_car",
    712: "bus",
}
SCHOOL_ROUTE_TYPES = frozenset({712})

# "Inbound" means travelling towards the nearest CBD anchor.
CBD_ANCHORS = (
    ("Wellington Station", -41.2782, 174.7800),
    ("Lambton Quay", -41.2830, 174.7757),
    ("Courtenay Place", -41.2935, 174.7800),
    ("Manners and Cuba", -41.2910, 174.7766),
)

# Used only for routes that do not run to the CBD (local routes between hubs).
REGIONAL_HUBS = (
    ("Queensgate", -41.2103, 174.9049),
    ("Petone Station", -41.2226, 174.8687),
    ("Waterloo", -41.2136, 174.9215),
    ("Naenae Station", -41.1985, 174.9463),
    ("Taita Station", -41.1803, 174.9607),
    ("Upper Hutt Station", -41.1260, 175.0705),
    ("Porirua Station", -41.1377, 174.8432),
    ("Johnsonville", -41.2233, 174.8048),
    ("Paraparaumu Station", -40.9165, 175.0074),
    ("Waikanae Station", -40.8766, 175.0662),
)

# Direction detection
DIRECTION_LOOKAHEAD_M = 500.0
DIRECTION_MIN_DELTA_M = 100.0
CBD_RADIUS_M = 2500.0
HUB_RADIUS_M = 800.0

# Stop pairing
PAIR_MAX_DISTANCE_M = 60.0
PAIR_MAX_DISTANCE_STRONG_M = 150.0
PAIR_MIN_SCORE = 0.5

# Departures
DEFAULT_DEPARTURE_LIMIT = 20
DEFAULT_DEPARTURE_HORIZON_HOURS = 72
MAX_DEPARTURE_HORIZON_HOURS = 168
