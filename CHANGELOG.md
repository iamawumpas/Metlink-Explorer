# Changelog

## v0.2.0 (2025-09-26) - MAJOR ARCHITECTURE CHANGE

### Breaking Changes
- **Complete Entity Restructure**: Changed from 2 route-based entities to individual stop-based entities
  - **New Entity Pattern**: `transport_type :: route_number / route_name :: stop_id / stop_description`
  - **Per-Stop Entities**: Creates one entity for each stop on the route (e.g., 23 entities for a 23-stop route)
  - **Stop-Specific Data**: Each entity shows next departures only for that specific stop
  - **Better User Experience**: Users can select specific stops without knowing stop IDs from website

### Features
- **Enhanced Config Flow**: Fixed API key validation logic for adding multiple routes
  - Integration now checks for existing API keys before asking user
  - Proper flow: Check existing key → Use existing OR ask for new → Select routes
  - Multiple route support without re-entering API credentials

- **Stop-Centric Data Model**: Each stop entity provides comprehensive stop-specific information
  - **State**: Next departure time for that specific stop
  - **Attributes**: Stop location, sequence, departures, real-time trip/vehicle data
  - **Stop Details**: Coordinates, zone information, stop codes for each stop
  - **Trip Tracking**: Real-time vehicle positions and delays for trips serving each stop

### Use Cases Enabled
- **Full Route Visualization**: Create cards displaying entire route with all stops
- **Specific Stop Monitoring**: Focus on particular stops of interest
- **Journey Planning**: See departures from origin stop to destination
- **Real-time Tracking**: Monitor vehicle progress stop-by-stop along route

### Technical Improvements
- Simplified API architecture focusing on stop-specific data requests
- Better error handling for stop-specific data failures
- Enhanced entity organization with route-based device grouping
- Improved debugging and logging for stop entity creation

## v0.1.2 (2025-09-26)

### Bug Fixes
- **Config Flow Error**: Fixed missing `async_step_init` method in OptionsFlowHandler
  - Added proper OptionsFlowHandler implementation to prevent "Handler OptionsFlowHandler doesn't support step init" error
  - Integration options flow now works correctly without throwing errors
  
- **Integration Initialization**: Enhanced setup error handling and debugging
  - Added comprehensive logging throughout integration setup process
  - Improved error handling in `async_setup_entry` to prevent silent failures
  - Added debug messages for coordinator initialization and platform setup
  - Fixed missing `integration_type: "hub"` in manifest.json

## v0.1.1 (2025-09-26)

### Bug Fixes
- **API Error Handling**: Fixed 400 Bad Request errors for invalid/empty stops
  - Enhanced `get_stop_times()` method with graceful error handling for stops without services
  - Added defensive programming in `get_route_departures()` to handle API failures
  - Individual stop failures no longer crash the entire departure lookup process
  - Improved debugging with detailed logging for API requests and responses
  - Integration now handles real-world API inconsistencies and invalid stop IDs

## v0.1.0 (2025-09-26)

### Major Enhancement - Direction-Specific Stop Sequences
- **Stop Sequence Integration**: Added complete stop sequences for both inbound and outbound routes
  - New `get_route_stops()` API method fetches all stops organized by direction
  - Enhanced `get_route_departures()` with direction filtering and stop sequence data
  - Each direction now has its own distinct stop sequence with proper ordering
  - Stop data includes coordinates, zone information, stop codes, and sequence positions

- **Enhanced Departure Information**: Next 10 departures now include comprehensive stop details
  - Departure times associated with specific stops and their position in route sequence
  - Stop coordinates (latitude/longitude) for mapping and distance calculations
  - Zone information for fare calculations
  - Stop codes and names for passenger information
  - Route stop sequence numbers for progress tracking

- **Improved Sensor Display**: Direction-specific state and attributes
  - State now shows: `"Next: 14:32:00 at Wellington Station (Stop 1)"`
  - Complete stop sequence available in sensor attributes for route visualization
  - Direction-specific departures ensure accurate inbound/outbound information
  - Enhanced attributes include total stop count and complete route mapping data

## v0.0.9 (2025-09-26)

### Bug Fixes
- **Sensor Unit Error**: Fixed ValueError preventing entity creation
  - Removed `native_unit_of_measurement` causing Home Assistant to expect numeric values
  - Added explicit `device_class = None` to indicate text-based sensor
  - Sensors now properly display string states like "No upcoming departures"
  - Fixed integration loading errors and entity registration issues

## v0.0.8 (2025-09-26)

### Features
- **Departure Functionality**: Added next 10 departures for selected routes
  - New `get_route_departures()` API method with time parsing and filtering
  - Enhanced coordinator to fetch departure data alongside real-time updates
  - Sensor state displays next departure time and stop name
  - Comprehensive departure attributes including stop information and trip details
  - Intelligent time filtering to show only upcoming departures
  - Integration of static GTFS schedule data with real-time updates

## v0.0.7 (2025-09-26)

### Bug Fixes
- **Coordinator DateTime**: Fixed AttributeError preventing entity creation
  - Replaced non-existent `last_update_success_time` property with `dt_util.utcnow()`
  - Fixed coordinator timestamp handling that was causing entity registration failures
  - Corrected corrupted manifest.json from previous fix attempt
  - Entities now properly register and display in Home Assistant

## v0.0.6 (2025-09-26)

### Bug Fixes
- **DateTime Attribute Error**: Fixed sensor attribute timestamp issues
  - Added defensive programming for datetime attribute handling in sensor.py
  - Enhanced `extra_state_attributes` with `hasattr()` checks for datetime objects
  - Fixed coordinator data access patterns to prevent AttributeError on timestamps
  - Improved error handling for sensor attribute generation

## v0.0.5 (2025-09-26)

### Bug Fixes
- **Entity Creation & Visibility**: Fixed dual entity creation issues
  - Only one entity was being created/visible instead of two (inbound/outbound)
  - Enhanced `unique_id` generation using `route_id` and `direction` for better uniqueness
  - Fixed device info to use route-specific identifiers instead of generic config entry ID
  - Removed manual `entity_id` assignment that could cause Home Assistant entity conflicts
  - Added detailed logging for entity creation debugging and troubleshooting
  - Fixed entity naming logic to ensure both directional entities are properly registered
  - Both entities should now appear in Developer Tools > States with correct naming

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