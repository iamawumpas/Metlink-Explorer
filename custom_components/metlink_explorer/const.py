"""Constants for the Metlink Explorer integration."""
from typing import Final

DOMAIN: Final = "metlink_explorer"

# API Configuration
API_BASE_URL: Final = "https://api.opendata.metlink.org.nz/v1"
API_TIMEOUT: Final = 30

# Transport Types mapping
TRANSPORT_TYPES: Final = {
    2: "Rail",
    3: "Bus", 
    4: "Ferry",
    5: "Cable Car",
    712: "School Services"
}

# Config Entry Keys
CONF_API_KEY: Final = "api_key"
CONF_TRANSPORT_TYPE: Final = "transport_type"
CONF_ROUTE_ID: Final = "route_id"
CONF_ROUTE_SHORT_NAME: Final = "route_short_name"
CONF_ROUTE_LONG_NAME: Final = "route_long_name"

# Update intervals
UPDATE_INTERVAL: Final = 300  # 5 minutes for regular updates