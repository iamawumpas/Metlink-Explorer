"""Constants for the Metlink Explorer integration."""

DOMAIN = "metlink_explorer"

# API Configuration
BASE_URL = "https://api.opendata.metlink.org.nz/v1"
API_ENDPOINTS = {
    "agency": "/gtfs/agency",
    "routes": "/gtfs/routes", 
    "stops": "/gtfs/stops",
    "trips": "/gtfs/trips",
    "stop_times": "/gtfs/stop_times",
    "calendar_dates": "/gtfs/calendar_dates",
    "vehicle_positions": "/gtfs-rt/vehiclepositions",
    "trip_updates": "/gtfs-rt/tripupdates",
    "service_alerts": "/gtfs-rt/servicealerts",
    "stop_predictions": "/stop-predictions"
}

# Transportation Types (GTFS route_type mapping)
TRANSPORTATION_TYPES = {
    2: "Train",
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

# Default Values
DEFAULT_SCAN_INTERVAL = 30  # seconds
REQUEST_TIMEOUT = 10  # seconds