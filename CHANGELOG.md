# Changelog

All notable changes to the Metlink Explorer Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.8] - 2025-09-30

### Enhancement — Tile-friendly attributes

- Added string summary attributes to improve display on Tile/Entity cards and other UIs that don't render arrays well:
  - `timeline_departure_stop_name`
  - `timeline_destination_stop_name`
  - `timeline_next_eta`
  - `timeline_next_departure`
  - `timeline_next_time_source`
  - `timeline_hub_stop_names` (list of hub names)
  - `timeline_preview` (compact "Stop Time • Stop Time • …")
  - `timeline_preview_times` (compact "HH:MM, HH:MM, …")
- No breaking changes; existing attributes remain unchanged.
- Complements 0.3.7’s direction-friendly naming fix.

## [0.3.7] - 2025-09-30

### Bug Fix — Direction-friendly naming

- Corrected direction naming logic for friendly names only:
  - Direction 0 now uses `route_desc`
  - Direction 1 now uses `route_long_name`
- This change affects display names only and does not change stop sequence or data retrieval.
- Example routes that benefit: HVL (Train), 83 (Bus).

## [0.3.6] - 2025-09-30

### Data Robustness and Performance (inspired by GTFS2)

- **Batch stop-predictions with concurrency**: Faster and more reliable collection of predictions across all stops on a route
- **Route matching hardening**: Match predictions by `route_id` or `route_short_name` with normalization
- **Service-day aware time handling**: Normalize `HH:MM` to `HH:MM:SS` and handle next-day rollover for ETAs
- **Static TTL caches**: Cache routes, stops, and stop patterns with a short TTL to reduce API calls
- **Trip updates fallback**: If `/stop-predictions` has gaps, blend in `/gtfs-rt/tripupdates` data for the same route/direction
- **Time source tagging**: Each timeline stop includes a `time_source` of `realtime`, `trip_update`, or `scheduled`

Minor: Improved changelog formatting and clarified acknowledgements for inspiration sources.

Acknowledgement: Several resilience ideas were inspired by the excellent GTFS2 project by vingerha (<https://github.com/vingerha/gtfs2>), particularly around tolerant matching, time normalization, and merging of real-time sources.

Acknowledgement: Actual project inspired by the Metlink Wellington Transport project by make-all (<https://github.com/make-all>)

### Developer Notes

- New helpers in `api.py`: `_batch_get_stop_predictions`, `_normalize_time_str`, `_eta_from_time_str`, `_prediction_matches_route`
- Caches added for: routes, stops, stop patterns, and route short names
- `get_route_timeline_for_card` now fetches predictions in batches, merges GTFS-RT trip updates as fallback, and annotates each stop with `time_source`

This release should improve stability when the upstream API deviates from strict standards and reduce latency for timeline rendering.

## [0.3.5] - 2025-09-29


### Timeline Card Display Feature

- **NEW: Route timeline for card display**: Added `get_route_timeline_for_card()` method to generate card-friendly stop data with ETA calculations
- **Real-time ETA calculations**: Shows "minutes and seconds from scheduled time" for each stop using real-time predictions
- **Smart stop categorization**: Automatically identifies departure stops, destination stops, and hub/interchange stops
- **Flexible time display**: Shows ETA in seconds ("30s"), minutes ("5m 30s"), or hours ("1h 15m") format based on time remaining
- **Enhanced sensor attributes**: Added `timeline_stops`, `departure_stop`, `destination_stop_timeline`, `hub_stops`, and `current_time` attributes
- **Fallback to scheduled times**: When real-time predictions aren't available, displays clearly marked scheduled GTFS times
- **Card-optimized data structure**: Each timeline stop includes `eta_display`, `eta_seconds`, `is_departure`, `is_destination`, `is_hub` flags for easy card rendering
- **Real-time status indicators**: Shows prediction count and real-time availability for each stop
- **Hub stop detection**: Automatically identifies major stations and interchanges using station name keywords

 
### Technical Improvements

- **Enhanced API integration**: Uses `/stop-predictions` endpoint for more accurate real-time data
- **Improved error handling**: Timeline generation continues working even if individual stop predictions fail
- **Better route matching**: Enhanced logic to match predictions using both route_id and route_short_name
- **Comprehensive logging**: Added detailed debug logging for timeline generation and ETA calculations
- **Performance optimization**: Efficient stop pattern processing and prediction matching

This version enables Home Assistant cards to display rich route timelines with:

- Selectable stops with real-time ETAs
- Always-visible departure and destination stops  
- Highlighted hub/interchange stops
- Clean time format display ("10:00, 10:03, 10:07" style)
- Real-time vs scheduled time indicators


## [0.3.4] - 2025-09-29

### Enhanced Real-time Data and Time Display

- **Improved real-time prediction matching**: Enhanced route matching logic to find predictions using both route_id and route_short_name
- **Better time display**: Clearly distinguish between real-time predictions and scheduled GTFS times
- **Enhanced debugging**: Added comprehensive logging for prediction matching and time handling
- **Time context indicators**: Scheduled times now prefixed with "Scheduled:" to avoid confusion
- **Additional prediction fields**: Support for expected_departure_time and expected_arrival_time fields
- **Enhanced debug info**: Added real-time vs scheduled stop counts and prediction statistics

This version improves the accuracy of departure times by better matching real-time predictions and clearly indicating when only scheduled times are available.


## [0.3.3] - 2025-09-29

### Critical Bug Fix - API Endpoint Parameter

- **Fixed 400 Bad Request error**: Added required `trip_id` parameter to `/gtfs/stop_times` endpoint call
- **Added fallback mechanism**: Stop pattern functionality is now optional and won't break basic integration
- **Improved error handling**: Integration continues working even if advanced stop features fail
- **API parameter compliance**: Fixed endpoint calls to match Metlink API documentation requirements

This fix resolves the "ConfigEntryNotReady" error and restores basic integration functionality.


## [0.3.2] - 2025-09-29

### Bug Fix - Stop Pattern Implementation

- **Fixed empty stop pattern data**: Resolved issue where `all_stops`, `next_departures`, and `destination_stop` attributes were empty
- **Enhanced route ID matching**: Improved comparison logic to handle both string and integer route IDs from API
- **Added comprehensive logging**: Added debug logging throughout the stop pattern process for better troubleshooting
- **Implemented fallback mechanism**: When real-time predictions are unavailable, integration now falls back to scheduled GTFS departure times
- **Improved error handling**: Better validation of API responses and data structures
- **Enhanced state attributes**: Added more detailed debugging information and scheduled departure times

### New Features

- **Mixed data sources**: Integration now shows both real-time predictions and scheduled times
- **Enhanced debugging**: Added `debug_info` attribute with troubleshooting information
- **Scheduled departure fallback**: Shows GTFS scheduled times when real-time data isn't available
- **Stop sequence validation**: Ensures stops are displayed in correct route order

### Technical Enhancements

- **String normalization**: Consistent handling of stop IDs and route IDs as strings
- **Better API error handling**: More resilient to individual stop prediction failures
- **Enhanced logging**: Debug-level logging for API calls and data processing
- **Data structure validation**: Validates API responses before processing

The integration should now properly display:
- Complete list of stops along the route in sequence
- Next scheduled bus arrival times (real-time or scheduled)
- Destination stop information
- Stop-by-stop departure predictions


## [0.3.1] - 2025-09-29

### New Feature

- Download stop information along the route. This implementation should:
  - Parse stop patterns for each route/direction using GTFS data
  - Identify destination stops (last stop in the sequence)
  - Fetch real-time predictions for all stops on the route
  - Provide rich sensor attributes including:

    - Complete stop list with sequences
    - Next departures across all stops
    - Destination information
    - Stop prediction counts



## [0.3.0] - 2025-09-29

### Version Bump

- new features to be added from here.



## [0.2.3] - 2025-09-29

### Bug Fixes — Entities not created

- no entities created. The AttributeError was preventing the entities from being created properly, which is why they were showing up as devices without entities and couldn't be added to dashboards.
- the key change is"
  **Before:** "last_updated": self.coordinator.last_update_success_time,
  **After:** "last_updated": self.coordinator.last_update_success,


## [0.2.2] - 2025-09-29

### Bug Fixes — Sensor recognition

- No entities created. The problem is in the sensor.py file — the entities need proper device_class, state_class, and unit_of_measurement properties to be recognized as proper sensors.
- The key changes are:
  - Added native_value property instead of state — This is the modern HA way
  - Added native_unit_of_measurement = "trips" — Defines what the sensor measures
  - Added state_class = SensorStateClass.MEASUREMENT — Marks it as a measurement sensor
  - Added device_info — Groups sensors under a device for better organization
  - Added available property — Shows if the sensor is available based on coordinator success
  - Added entity_registry_enabled_default = True — Ensures entities are enabled by default




## [0.2.1] - 2025-09-29

### Bug Fix — Integration entries naming

- corrected the ***Integration entries*** naming scheme to **title = f"{transportation_name} :: {route_short_name} / {route_long_name}"**



## [0.2.0] - 2025-09-29

### Version Bump — initial integration

- initial integration is ready for testing



## [0.1.4] - 2025-09-28


### Added

- **Step 4 Complete**: Entity Creation with Direction-Based Naming
- **Dual Entity Creation**: Each route now creates two sensor entities (Direction 0 and Direction 1)
- **GTFS-Based Naming**: Uses authentic GTFS `route_desc` field for Direction 1 descriptions
- **Simplified Entity Names**: Changed from `Transportation Type :: Route / Description` to `Route :: Description`
- **Real-Time Data Integration**: Sensors provide live trip counts and vehicle position data

### Changed

- **Entity Naming Schema**: Now uses `route_short_name :: route_description` format
- **Direction Logic**: Direction 0 uses `route_long_name`, Direction 1 uses `route_desc`
- **Configuration Storage**: Added `CONF_ROUTE_DESC` to store Direction 1 descriptions
- **Sensor Attributes**: Updated to reflect new naming and include direction-specific data

### Technical Details — Route selection

- Direction 0: `route_short_name :: route_long_name` (e.g., "83 :: Wellington - Eastbourne")  
- Direction 1: `route_short_name :: route_desc` (e.g., "83 :: Eastbourne - Wellington")
- Real-time trip counting per direction
- Enhanced sensor state attributes with direction-specific information
- Improved error handling for missing route descriptions



## [0.1.3] - 2025-09-28

### Added — Route selection and filtering

- **Enhanced Route Selection (Step 3)**: Implemented intelligent alphanumeric sorting for route IDs
- **Smart Route Filtering**: Routes are now filtered to exclude already-configured routes
- **Advanced Sorting Logic**: Handles mixed numeric/text route IDs properly (e.g., "1", "31x", "83", "220", "AX", "CCL")
- **Improved Route Display**: Route options now show "route_short_name :: route_long_name" format
- **Regular Expression Support**: Added regex-based parsing for complex route naming patterns

### Technical Details

- Sort priority: Numeric routes (0), Text routes (1), Empty/invalid routes (2)
- Numeric routes are sorted numerically first, then by any text suffix
- Mixed alphanumeric routes (like "31x", "60e") are sorted by number then letter
- Pure text routes are sorted alphabetically
- Enhanced error handling for edge cases in route data



## [0.1.2] - 2025-09-28

### Changed the logo path to display correctly in HACS

- new image location is <https://raw.githubusercontent.com/iamawumpas/Metlink-Explorer/main/custom_components/metlink_explorer/assets/logo%20(256x256).png>
- based on the following information:

__ The most common reason for images in a GitHub repository's README.md to appear as broken picture icons within HACS (Home Assistant Community Store) is an incorrect image path, especially when using relative links.

HACS is essentially rendering the GitHub repository's README file. If the markdown for the image link is not a fully qualified URL or an explicitly correct relative path, the image won't load.

Here are the primary causes and corresponding fixes:

1. Incorrect Paths (Most Common)
The way a path works on your local machine can differ from how it's interpreted on GitHub and subsequently rendered by HACS.

Problem: You are using a relative path like ![Screenshot](images/myimage.png). This works perfectly on GitHub's website. However, HACS's renderer may not correctly resolve the relative path from the context it loads the README.

Solution: Use the Full "Raw" GitHub URL
The most reliable method is to use the direct link to the image file, which is served from raw.githubusercontent.com.

In your GitHub repository, navigate to the image file (e.g., images/myimage.png).

Click the "Raw" button.


Copy the URL from your browser's address bar. It will look something like this:
<https://raw.githubusercontent.com/USER/REPO/BRANCH/path/to/image.png>

Use this absolute URL in your README.md file:

Markdown

![Alt Text](https://raw.githubusercontent.com/USER/REPO/BRANCH/path/to/image.png)
This method guarantees the HACS renderer has a direct, absolute link to the image resource. __



## [0.1.1] - 2025-09-28

### Added - Step 2 Complete: Intelligent Transportation Type Selection
- **✅ STEP 2 IMPLEMENTED**: Smart transportation type filtering with route availability checking
- Intelligent filtering: Only shows transportation types that have available (unconfigured) routes
- Route count display: Shows how many routes are available for each transportation type
- Prevents user confusion by hiding transportation types with no available routes
- Enhanced user experience with informative footnote explaining filtering logic

### Smart Route Management

- `_get_available_transportation_types()` - Filters transport types by route availability
- `_get_available_routes_for_type()` - Gets unconfigured routes for each transport type
- Prevents duplicate route configurations across integration entries
- Example: Ferry service with 2 routes will be hidden if both routes are already configured

### Enhanced User Interface

- Updated translations with explanatory footnote about transportation type filtering
- New error messages for cases where no transportation types or routes are available
- Clear indicators showing route counts for each available transportation type
- Improved user guidance in both `strings.json` and `translations/en.json`

### Technical Implementation — Step 2

- Cross-entry route tracking to prevent duplicates
- Dynamic transportation type option generation based on availability
- Comprehensive error handling for edge cases
- All Step 2 requirements met with intelligent route management



## [0.1.0] - 2025-09-28

### Added — Step 1 Complete: API Key Validation

- **✅ STEP 1 IMPLEMENTED**: Complete API key validation functionality
- API key validation using `/gtfs/agency` endpoint with 23 agencies detected
- Automatic reuse of existing API keys from other integration entries
- Comprehensive error handling for invalid keys and connection issues
- Enhanced user interface with clear setup instructions in translations
- Live API testing confirmed working with actual Metlink Open Data API
- Updated manifest.json and README.md version synchronization to 0.1.0

### Technical Implementation — Step 1

- `MetlinkApiClient.validate_api_key()` - Tests connection to Metlink API
- `config_flow.py` - Smart API key detection and validation flow
- `translations/en.json` - Improved user guidance and setup instructions
- Proper error handling for network issues and invalid credentials
- All Step 1 requirements met and thoroughly tested

### Development Workflow

- Established consistent version management across manifest.json, README.md, and CHANGELOG.md
- Ready to proceed to Step 2 (Transportation Type Selection)



## [0.0.3] - 2025-09-27

### Modified Header in README.md

- Converted the heading format into a table to better ensure logo placement. Not ideal as the default table formatting shows the borders



## [0.0.2] - 2025-09-27

### Initial README.md formatting

- uploaded an 80x80 logo to \assets
- uploaded a 256x256 logo to \assets
- initial layout for heading.



## [0.0.1] - 2025-09-27

### Added - Initial Project Structure

- Created Home Assistant custom component file structure
- Added `manifest.json` with integration metadata
- Implemented API client foundation for Metlink Open Data API
- Created configuration flow setup wizard
- Added sensor platform structure for route monitoring
- Implemented internationalization support with English translations
- Set up project documentation and README

### Technical Implementation

- **API Integration**: Base client for Metlink Open Data API (`api.py`)
- **Configuration Flow**: Multi-step setup wizard (`config_flow.py`)
  - Step 1: API key validation and storage
  - Step 2: Transportation type selection (Bus, Train, Ferry, Cable Car, School Bus)
  - Step 3: Route selection with filtering and sorting
  - Step 4: Entity creation with direction-based naming
- **Sensor Platform**: Route monitoring entities (`sensor.py`)
- **Constants**: API endpoints and transportation type mappings (`const.py`)
- **Translations**: English UI strings (`strings.json`, `translations/en.json`)

### Project Structure

```text
custom_components/metlink_explorer/
├── __init__.py                 # Integration setup
├── api.py                      # Metlink API client
├── config_flow.py             # Setup wizard
├── const.py                   # Constants and configuration
├── manifest.json              # Integration metadata
├── sensor.py                  # Sensor entities
├── strings.json               # UI strings
├── assets/
│   └── logo_placeholder.md    # Logo placeholder (need 256x256 PNG)
└── translations/
    └── en.json               # English translations
```

### Features Implemented

- **API Key Management**: Reuses existing API keys from other entries
- **Transportation Type Mapping**: GTFS route_type support for all Wellington transport modes
- **Route Sorting**: Alphanumeric sorting with proper numeric handling
- **Direction Logic**:
  - Direction 0: Uses `route_long_name` as-is
  - Direction 1: Reverses `route_desc` using ' - ' delimiters
- **Entity Naming Convention**: `transportation-type :: route_number / route_description`
- **Real-time Data Support**: Vehicle positions, trip updates, stop predictions
- **Error Handling**: Comprehensive API error handling and user feedback

### Next Steps

- [ ] Add integration logo (256x256 PNG)
- [ ] Test API integration and config flow
- [ ] Implement real-time data processing
- [ ] Add more sensor attributes and state information
- [ ] Enhance error handling and user feedback

---

## Development Guidelines

- **Version Format**: `x.y.z` where:
  - `z` = Incremental changes to the code
  - `y` = Major feature bumps (determined by maintainer)
  - `x` = Published version (determined by maintainer)
- **Commit Format**: Each commit includes the version number in the message
- **Manifest Updates**: Version number must be updated in `manifest.json` for each change
