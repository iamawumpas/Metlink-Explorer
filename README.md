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
  <strong>Version:</strong> 2.9.0
    </td>
  </tr>
</table>

A Home Assistant custom integration that brings Wellington public transport from the Metlink Open Data API into Home Assistant as a data service for dashboard cards.

> **Version 2 is a rebuild and is not compatible with version 1.** Entities, setup options and card configuration have all changed. See the [changelog](CHANGELOG.md) for what changed and why. Version 1 code is no longer included in this repository.

## Features

- **Departure board**: search for several stops (up to 8), each shown as a coloured chip, and choose where you are heading from each ("Towards Courtenay Place"). Departures are grouped by stop, with every route and the destination on each row. Delays, early running, cancellations and skipped stops are merged in, and departures after today show the day ("Tue 08:43 AM").
- **Whole network timetable**: all Metlink routes and stops are downloaded once, stored on disk and checked for changes every day. Bus, train, ferry and cable car are included, and school buses are flagged.
- **Gentle on the API**: nothing is requested from Metlink while no card is open, and one failing feed never stops another.
- **Live map**: the `metlink-map-card` shows live buses, trains and ferries, route lines and stops on a Leaflet map limited to the Wellington region. Use the mode buttons (Bus, Train, Ferry, Cable car) and the Filters panel to choose routes, route colours, stop colour and size, the map style and how much to darken it. Your Home Assistant home zone is shown. Until you choose something, it is just a map.
- **Service alerts**: the map shows an alerts button when alerts affect your selection. Alerts are colour coded by severity.
- **Ferries via AISStream**: ferry positions come from one shared AISStream connection (the AISStream key is optional). It only runs while a map card is open and can never affect the bus and train data.
- **No entities to manage**: the integration is a data service. Your choices are saved to your Home Assistant user, so they follow you between browsers and devices. Existing browser-saved choices are imported the first time that user opens a card.

Add the cards from the dashboard card picker: **Metlink Departure Board** and **Metlink Map**.

### Card options (YAML)

All options are optional.

**Metlink Departure Board** (`custom:metlink-departure-board-card`)

| Option | Meaning |
|---|---|
| `height` | Card height in pixels (`500`) or any CSS size (`60vh`). Without it, drag the bottom-right corner to resize. |
| `records` | Show only the next N departures for each stop, for example `3`. |
| `limit` | Departures fetched per stop. Default 10. |
| `id` | Gives this card its own saved choices if you use more than one. |
| `map_id` | The `id` of the map card whose route colours the board should follow. |

**Metlink Map** (`custom:metlink-map-card`)

| Option | Meaning |
|---|---|
| `height` | Fixed height. Without it, the map fills the screen height. |
| `basemap` | Map style. |
| `popup_theme` | Popup theme. |
| `dim` | How much to darken the map. |
| `start_zoom` | Zoom the map opens at (8 to 19, default 14), centred on your home. |
| `stop_color`, `stop_size` | Stop marker colour and size. |
| `routes` | Routes to show at start. |
| `modes` | Modes to show at start, for example `[bus, train]`. |
| `id` | Gives this card its own saved choices if you use more than one. |

## Data sources

Metlink data is published by the Greater Wellington Regional Council under the Creative Commons Attribution 4.0 licence. Live ferry positions come from [AISStream](https://aisstream.io/), which publishes no formal terms. The map credits both.


## Why this integration?
Simply put I got frustrated :smile: trying to make my dashboard do things the entities couldn't/wouldn't/probably shouldn't do. It turns out that while the Metlink API uses the GTFS standard for publishing its scheduling data and real-time data, it does not fully conform to the standard. The result is many fields do not behave the way they were meant to, contain different data, or data is formatted incorrectly. I wanted an integration that gathers all of the data, fixes many of these problems, and serves it to custom cards.


## Installation

You can install Metlink Explorer either manually or via HACS as a custom repository.

### Option A — Manual Installation

1. Download or clone this repository
2. Copy the entire `custom_components/metlink_explorer` directory into your Home Assistant `config/custom_components` folder
  - Final path should be: `<config>/custom_components/metlink_explorer`
3. Restart Home Assistant
4. Go to **Settings** > **Devices & Services** > **Add Integration**
5. Search for "Metlink Explorer" and follow the setup wizard

### Option B — Install via HACS (Custom Repository)

Prerequisite: HACS is installed in your Home Assistant. If you don’t have HACS yet, see [Installing HACS](#installing-hacs).

1. In Home Assistant, open **HACS**
2. Click the three dots menu (⋮) > **Custom repositories**
3. Add repository URL: `https://github.com/iamawumpas/Metlink-Explorer`
    - Category: "Integration"
4. Click **Add**
5. Find "Metlink Explorer" in HACS > Integrations and click **Download**
6. Restart Home Assistant when prompted
7. Go to **Settings** > **Devices & Services** > **Add Integration**
8. Search for "Metlink Explorer" and complete the setup

## Installing HACS

HACS (Home Assistant Community Store) is the recommended way to discover and manage third‑party integrations like this one.

Quick guide:

1. Ensure Home Assistant “Advanced Mode” is enabled (Profile > Advanced Mode)
2. Follow the official HACS installation guide:
  - Prerequisites: https://hacs.xyz/docs/setup/prerequisites
  - Installation: https://hacs.xyz/docs/setup/download/
3. Restart Home Assistant after installing HACS
4. Add the HACS integration: Settings > Devices & Services > Add Integration > search for “HACS” and complete onboarding
5. After HACS is set up, return to “Option B — Install via HACS” above

## Setup Process

1. **API keys**: Enter your Metlink Open Data API key (get one free from [Metlink Developer Portal](https://opendata.metlink.org.nz/)). The AISStream key is optional.
2. **Wait for the first timetable download**: it runs in the background and can take several minutes. Home Assistant is not held up.
3. **Add the card**: edit a dashboard, add the **Metlink Departure Board** card, search for your stop and choose where you are heading.

You can change the keys later from the integration's **Reconfigure** option.

## Development

See [CHANGELOG.md](CHANGELOG.md) for development progress and version history.

## Support

- **Issues**: [GitHub Issues](https://github.com/iamawumpus/Metlink-Explorer/issues)  
- **API Documentation**: [Metlink Open Data Portal](https://opendata.metlink.org.nz/)
- **Home Assistant**: [Custom Components Documentation](https://developers.home-assistant.io/docs/creating_component_index/)


## Acknowledgments
Inspiration for this integration go to the following HACS Integrations:
 - GTFS2 for Static and RealTime Public transport status collecting in Home Assistant https://github.com/vingerha/gtfs2
 - Metlink Wellington Transport for Home Assistant https://github.com/make-all/metlink-nz

      Thanks for creating great tools and inspiring me to try my own.