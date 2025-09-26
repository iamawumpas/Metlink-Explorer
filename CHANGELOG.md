# Changelog

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