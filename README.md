<table>
  <tr>
    <td>
      <img src="https://raw.githubusercontent.com/iamawumpas/Metlink-Explorer/main/custom_components/metlink_explorer/assets/logo%20(256x256).png" alt="Metlink Explorer Logo" width="auto" height="100px">
    </td>
    <td>
      <h1>Metlink Explorer</h1>
      Let's do public transport!<img width="550" height="0">
    </td>
  </tr>
  <tr>
    <td colspan="2" style="border: none; padding-top: 0.5em;">
      <strong>Version:</strong> 0.1.4
    </td>
  </tr>
</table>

A Home Assistant custom component that integrates with the Metlink Open Data API to provide real-time Wellington public transport information as sensor entities.

## Features

- **Multi-Modal Transport Support**: Bus, Train, Ferry, Cable Car, and School Bus routes
- **Real-Time Data**: Vehicle positions, trip updates, and service alerts
- **Direction-Based Entities**: Separate sensors for each route direction with intelligent naming
- **Easy Setup**: Step-by-step configuration flow with API key validation
- **Route Filtering**: Select routes by transportation type with alphanumeric sorting

## Installation

1. Copy the `custom_components/metlink_explorer` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** > **Integrations** > **Add Integration**
4. Search for "Metlink Explorer" and follow the setup wizard

## Setup Process

1. **API Key**: Enter your Metlink Open Data API key (get one free from [Metlink Developer Portal](https://opendata.metlink.org.nz/))
2. **Transport Type**: Choose from Bus, Train, Ferry, Cable Car, or School Bus
3. **Route Selection**: Pick a specific route from the filtered list
4. **Entities Created**: Two sensors are created (one for each direction)

## Entity Naming Convention

Entities are named using the format: `Route Number :: Route Description`

- **Direction 0**: `route_short_name :: route_long_name` 
- **Direction 1**: `route_short_name :: route_desc`

The GTFS data provides separate descriptions for each direction:
- `route_long_name` contains the Direction 0 route description
- `route_desc` contains the Direction 1 route description

Example:
- `83 :: Wellington Station - Petone - Lower Hutt - Eastbourne` (Direction 0)
- `83 :: Eastbourne - Lower Hutt - Petone - Wellington Station` (Direction 1)

## Development

See [CHANGELOG.md](CHANGELOG.md) for development progress and version history.

## Support

- **Issues**: [GitHub Issues](https://github.com/iamawumpus/Metlink-Explorer/issues)  
- **API Documentation**: [Metlink Open Data Portal](https://opendata.metlink.org.nz/)
- **Home Assistant**: [Custom Components Documentation](https://developers.home-assistant.io/docs/creating_component_index/)