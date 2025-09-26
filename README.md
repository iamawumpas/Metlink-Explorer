# Metlink Explorer

A Home Assistant integration to monitor Metlink Wellington (NZ) public transport schedules, alerts, and real-time information.

## Features

- Monitor real-time bus, train, ferry, cable car, and school services
- Track route status with directional support (inbound/outbound)
- View service alerts and disruptions
- Real-time vehicle positions and trip updates
- Easy setup through Home Assistant UI

## Installation

### Manual Installation

1. Copy the `custom_components/metlink_explorer` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration > Integrations
4. Click the "+" button and search for "Metlink Explorer"

## Configuration

1. Get your API key from [Metlink Open Data API](https://api.metlink.org.nz/)
2. Add the integration through the Home Assistant UI
3. Enter your API key
4. Select the transport type you want to monitor
5. Choose the specific route from the dropdown

The integration will create two sensors for each route:
- One for the outbound direction (direction 0)
- One for the inbound direction (direction 1)

## Entity Naming

Entities are named using the format:
`{transport_type} :: {route_number} / {route_description}`

For example:
- `Bus :: 83 / Wellington - Petone - Lower Hutt - Eastbourne` (outbound)
- `Bus :: 83 / Eastbourne - Lower Hutt - Petone - Wellington` (inbound)

## Supported Data

The integration provides:
- Route information (colors, agency, etc.)
- Real-time trip updates with delays
- Vehicle positions and tracking
- Service alerts and disruptions
- Stop information and schedules

## API Rate Limits

Please be mindful of Metlink's API rate limits. The integration updates every 5 minutes by default.

## Version History

- v0.0.1: Initial release with basic route monitoring and config flow

## License

This project is licensed under the MIT License.
