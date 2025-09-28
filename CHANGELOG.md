# Changelog

All notable changes to the Metlink Explorer Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Technical Implementation
- Cross-entry route tracking to prevent duplicates
- Dynamic transportation type option generation based on availability
- Comprehensive error handling for edge cases
- All Step 2 requirements met with intelligent route management

## [0.1.0] - 2025-09-28

### Added - Step 1 Complete: API Key Validation
- **✅ STEP 1 IMPLEMENTED**: Complete API key validation functionality
- API key validation using `/gtfs/agency` endpoint with 23 agencies detected
- Automatic reuse of existing API keys from other integration entries
- Comprehensive error handling for invalid keys and connection issues
- Enhanced user interface with clear setup instructions in translations
- Live API testing confirmed working with actual Metlink Open Data API
- Updated manifest.json and README.md version synchronization to 0.1.0

### Technical Implementation
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
```
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