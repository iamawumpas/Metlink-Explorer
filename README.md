# ![Metlink Explorer Logo](assets/logo.png) Metlink Explorer: 
# a Home Assistant integration
This is a custom component for Home Assistant to update Metlink Wellington, NZ departure info in real time. It provides bus, train, and ferry schedules, as well as general alerts, alternative transportation alerts, and cancellations.

This integration can be used with most Lovelace Cards (Entity, entities, tile, markdown, and maybe others), but not all of the attributes (see the table below) may be available. This integration also installs a custom card that shows Tube/Metro style route information for your selected route. See ***How to use the Metro Card*** for instructions.
<hr><br><br>

## $${\color{red} NOT \space IN \space PRODUCTION}$$
This integration is a PPP (Personal Passion Project) for me and is currently not suitable for use in Home Assistant... yet! Watch this space.
<hr><br><br>

## Before Installing
To use the Metlink Wellington schedules you will need to create an account on the [Metlink Open Data Developer Portal](https://opendata.metlink.org.nz/). Once signed in, an API key will be created for you and you can copy and paste this key into the integration. For more information, log in to the Metlink Open Data Developer Portal and read *Getting Started*.

## Installation
This integration is installed using HACS (Home Assistant Community Store). Follow these instructions:

1. **Open Home Assistant.**
2. Go to **HACS** in the sidebar. If you haven’t installed HACS yet, follow the [official HACS installation guide](https://hacs.xyz/docs/setup/download/).
3. Click on **Integrations**.
4. Click the **three dots menu** (⋮) in the top right and select **Custom repositories**.
5. Enter the URL of this repository (`https://github.com/iamawumpas/Metlink-Explorer`) and select **Integration** as the category.
6. Click **Add**.
7. Find **Metlink Explorer** in the list of integrations and click **Install**.
8. **Restart Home Assistant** after installation.
9. Go to **Settings → Devices & Services → Add Integration** and search for **Metlink Explorer**.
10. Follow the prompts to configure your API key and select your routes. More details are below.

## How to use the Metlink Explorer integration

1. **Add the Integration:**
   - Go to **Settings → Devices & Services → Add Integration** in Home Assistant.
   - Search for **Metlink Explorer** and select it.

2. **Enter Your API Key:**
   - When prompted, paste your Metlink API key (see "Before Installing" above if you need to get one).

3. **Choose a Transport Type:**
   - Select whether you want to add a **Train**, **Bus**, or **Ferry** route.

4. **Select a Route:**
   - Pick the specific route you want to monitor from the dropdown list.
   - Only routes that you haven’t already added will be shown.

5. **Finish Setup:**
   - Complete the setup. The integration will create a sensor for the selected route.

6. **Add More Routes (Optional):**
   - To monitor additional routes, repeat the steps above. Each route will appear as a separate sensor.

7. **View Your Data:**
   - Go to **Developer Tools → States** or add the sensor to your dashboard to see real-time departures, alerts, cancellations, and more.

Each integration entry will contain a maximum of two entities, representing the outbound and inbound directions for the selected route.

Each entity is labelled using this format:
**Vehicle type :: route number - route name**

*Examples:*
- Bus :: 83 - Eastbourne - Lower Hutt - Petone - Wellington
- Ferry :: QDF - Days Bay - Queens Wharf
- Train :: KPL - Kāpiti Line (Waikanae - Wellington)

**Tip:**
You can use the sensor’s attributes in dashboards, automations, and templates. See the table below for available attributes.

**Note:**
If you do not see the integration after installation, clear your browser cache and restart Home Assistant.
<hr>

### Available Attributes

| Attribute Name          | Description                                                                                          |
|------------------------ |------------------------------------------------------------------------------------------------------|
| `route_stops`           | List of all stops for the selected route, including stop name, scheduled departure, and real-time predictions. |
| `alerts`                | List of active service alerts affecting this route (e.g., disruptions, delays, notices).             |
| `trip_updates`          | List of real-time trip updates for this route (e.g., delays, changes in schedule).                   |
| `cancellations`         | List of trip cancellations for this route.                                                           |
| `departure_predictions` | List of real-time departure predictions for each stop on this route.                                 |
| `route_name`            | The name of the route (e.g., "WRL - Wairarapa Line (Masterton - Wellington)").                       |
| `departure_name`        | The name of the departure (first) stop for this route.                                               |
| `destination_name`      | The name of the destination (last) stop for this route.                                              |
| `trip_start_time`       | Scheduled departure time from the first stop of the trip.                                            |
| `trip_end_time`         | Scheduled (or real-time, if available) arrival time at the last stop of the trip.                    |