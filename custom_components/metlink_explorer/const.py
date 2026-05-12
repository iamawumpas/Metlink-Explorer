"""Constants for the Metlink Explorer integration."""

DOMAIN = "metlink_explorer"

# API Configuration
BASE_URL = "https://api.opendata.metlink.org.nz/v1"
API_ENDPOINTS = {
    "agency": "/gtfs/agency",
    "routes": "/gtfs/routes", 
    "stops": "/gtfs/stops",
    "trips": "/gtfs/trips",
    "stop_times": "/gtfs/stop_times",  # NEW: Needed for stop sequences
    "shapes": "/gtfs/shapes",
    "calendar_dates": "/gtfs/calendar_dates",
    "vehicle_positions": "/gtfs-rt/vehiclepositions",
    "trip_updates": "/gtfs-rt/tripupdates",
    "service_alerts": "/gtfs-rt/servicealerts",
    "stop_predictions": "/stop-predictions"
}

# Transportation Types (GTFS route_type mapping)
TRAIN_ROUTE_TYPE = 2

TRANSPORTATION_TYPES = {
    TRAIN_ROUTE_TYPE: "Train",
    3: "Bus", 
    4: "Ferry",
    5: "Cable Car",
    712: "School Bus"
}

# Configuration Keys
CONF_API_KEY = "api_key"
CONF_TRANSPORTATION_TYPE = "transportation_type"
CONF_ROUTE_ID = "route_id"
CONF_ROUTE_SHORT_NAME = "route_short_name"
CONF_ROUTE_LONG_NAME = "route_long_name"
CONF_ROUTE_DESC = "route_desc"
CONF_ROUTES = "routes"
CONF_ACTIVE_DIRECTION = "active_direction"
CONF_LEGACY_DIRECTION_ENTITIES = "legacy_direction_entities"
CONF_AIS_API_KEY = "ais_api_key"

# Default Values
DEFAULT_SCAN_INTERVAL = 30  # Aligned with Metlink backend update frequency and new RTI system
REQUEST_TIMEOUT = 15  # Increased timeout for complex requests
DEFAULT_ACTIVE_DIRECTION = 0
DEFAULT_GTFS_CACHE_TTL_SECONDS = 300
TRAIN_GTFS_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
TRAIN_GEOMETRY_SENSOR_KEY = "train_route_geometry"

# AIS ferry live tracking
FERRY_ROUTE_TYPE = 4
EAST_BY_WEST_FLEET_URL = "https://eastbywest.co.nz/about-us/our-fleet/"
AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"
AISSTREAM_DEFAULT_BBOX = [[[-41.38, 174.73], [-41.21, 174.92]]]
AISSTREAM_SAMPLE_SECONDS = 2.5
AISSTREAM_POSITION_CACHE_SECONDS = 20
AIS_VESSEL_REFRESH_SECONDS = 24 * 60 * 60
AIS_FERRY_SEED_NAMES = [
    "IKA RERE",
    "COBALT",
    "CITY CAT",
]