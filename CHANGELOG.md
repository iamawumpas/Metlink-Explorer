# Changelog

## v0.0.4 (2025-09-26)

### Bug Fixes
- **GTFS-RT Data Handling**: Fixed AttributeError during data coordinator updates
  - GTFS-RT APIs return `{header, entity}` structure, not direct arrays  
  - Updated API client to properly extract `entity` arrays from GTFS-RT responses
  - Fixed coordinator filtering logic for `trip_updates`, `vehicle_positions`, `service_alerts`
  - Updated sensor.py to handle proper GTFS-RT entity structure access patterns
  - Handle `route_id` as integer from API and convert to string for comparison
  - Fixed `trip_update`, `vehicle`, and `alert` data access in entity attributes
  - This resolves the `'str' object has no attribute 'get'` error during data updates

## v0.0.3 (2025-09-26)

### Bug Fixes
- **Config Flow**: Fixed KeyError crash during route selection step
  - Route selection form only provided `route_id`, but code expected `route_short_name` and `route_long_name`
  - Updated logic to look up route details via API when `route_id` is selected
  - Simplified `_create_entry` method to avoid duplicate API calls
  - Integration setup flow now completes successfully without errors

## v0.0.2 (2025-09-26)

### HACS Compatibility
- Added `hacs.json` for proper HACS integration support
- Fixed version format in `manifest.json` (removed 'v' prefix)
- Added proper Git tags for version detection
- HACS now correctly shows version instead of commit hash

## v0.0.1 (2025-09-26)

### Features
- Initial release of Metlink Explorer integration
- API key validation and configuration flow
- Transport type selection (Bus, Rail, Ferry, Cable Car, School Services)
- Route selection with alphanumeric sorting
- Dual entity creation for inbound/outbound directions
- Real-time data collection from Metlink API
- Service alerts and trip updates
- Vehicle position tracking
- Custom entity naming with directional route descriptions

### Integration Features
- **Step 1**: API key validation using existing entities or user input
- **Step 2**: Transport type selection with radio button interface
- **Step 3**: Route filtering and dropdown selection
- **Step 4**: Entity creation with proper naming schema

### Entity Naming Schema
- Integration Entry: `{transport_type} :: {route_number} / {route_description}`
- Direction 0 (Outbound): Route name as provided by API
- Direction 1 (Inbound): Route name reversed using ' - ' delimiters

### API Support
- GTFS static data (routes, stops, agencies)
- GTFS-RT real-time data (trip updates, vehicle positions, service alerts)
- Automatic data updates every 5 minutes
- Proper error handling and connection management

### Technical Implementation
- Custom config flow with multi-step setup
- Data coordinator for efficient API management
- Sensor entities with rich attribute data
- Translation support for UI elements
- Device info and entity categorization