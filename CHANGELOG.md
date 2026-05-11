# Changelog

All notable changes to the Metlink Explorer Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.1] - 2026-05-12

### Improvement - Layer panel readability and labeling polish

- Increased layer panel section heading prominence (larger, bolder, brighter text) for quicker scanning.
- Removed excess right-side panel spacing so the control box hugs button content more tightly.
- Renamed the panel heading to `Display Layers` for clearer intent.
- Updated frontend build marker to `0.11.1`.

## [0.11.0] - 2026-05-12

### Feature - Per-mode layer visibility toggle panel

- Added a hamburger menu button in the top-left corner of the map card that opens a layer control panel.
- Panel contains three sections — **Routes**, **Stops**, and **Live Tracking** — each showing one toggle button per configured vehicle mode (Train, Bus, Ferry, Cable Car).
- Clicking a button toggles that layer group on or off instantly; active layers show as white filled pills, hidden layers appear dimmed.
- Only modes that have entities configured in the card YAML appear in the panel, so unused rows are never shown.
- Toggle state auto-reverts to the card YAML defaults after 10 minutes of no user interaction.
- All three layer types (route lines, stop markers, live vehicle badges) are tracked by mode in separate internal registries so toggles can target individual MapLibre layers precisely.
- Updated frontend build marker to `0.11.0`.

## [0.10.14] - 2026-05-12

### Improvement - Ferry stop marker shape changed to square

- Changed the ferry stop hub marker from an equilateral triangle to a square shape.
- Retained the cyan (`#12cfe3`) background fill and white border.
- Updated the ferry icon overlay clip region to match the new square boundary.
- Added layer visibility state tracking infrastructure in the map card (groundwork for upcoming per-mode layer toggle controls).
- Updated frontend build marker to `0.10.14`.

## [0.10.13] - 2026-05-12

### Improvement - Restore ferry icon to original size with refined crop

- Restored the ferry icon overlay to its original size inside the stop marker triangle.
- Kept the newer ferry silhouette crop, background transparency cleanup, alignment offset, and triangle clipping.
- Retained the cyan ferry triangle background with the white border.
- Updated frontend build marker to `0.10.13`.

## [0.10.12] - 2026-05-12

### Improvement - Refine ferry stop icon composition inside the triangle

- Cropped the `ferry-stop.png` overlay to the visible ferry silhouette and stripped its solid background before drawing it.
- Increased the rendered ferry icon size by 25% so the vessel itself is more prominent inside the stop marker.
- Updated the ferry stop triangle background to cyan while keeping the white border and triangle clip.
- Updated frontend build marker to `0.10.12`.

## [0.10.11] - 2026-05-11

### Improvement - Use dedicated ferry and train stop marker assets

- Added a dedicated `ferry-stop.png` frontend marker asset for ferry stop hubs, using the same image-loading path as bus stops.
- Updated train stop hub markers to load the renamed `train-stop.png` asset instead of the old `train.png` filename.
- Kept the existing canvas marker fallbacks so stop markers still render if either asset is unavailable.
- Updated frontend build marker to `0.10.11`.

## [0.10.10] - 2026-05-11

### Fix - Ferry stop marker size matches bus stops

- Updated ferry stop marker sizing so ferry triangles now use the same width and height as bus stop markers.
- Left the existing ferry triangle shape intact while aligning its rendered diameter with bus stops.
- Updated frontend build marker to `0.10.10`.

## [0.10.9] - 2026-05-11

### Improvement - Inline direction chip beside route ID in departure bubble

- Updated departure bubble row layout to render the direction chip (`Inbound`/`Outbound`) inline with the route ID to reduce vertical space usage.
- Kept existing mode-agnostic direction-tag logic so the same inline behavior applies to train, bus, ferry, and cable car rows.
- Updated frontend build marker to `0.10.9`.

## [0.10.8] - 2026-05-11

### Fix - Merge train platform stop IDs into one station marker and bubble

- Added train station grouping in the map card by normalizing trailing platform digits in stop IDs (for example `WATE1`/`WATE2`, `WELL2`/`WELL3`).
- Train departure bubble stop matching now includes sibling platform IDs under the same station key.
- Train marker generation now deduplicates by normalized station ID to avoid duplicate station names/markers.
- Train bubble dedupe keys now use station-normalized stop IDs to avoid repeated rows after platform merge.
- Updated frontend build marker to `0.10.8`.

## [0.10.7] - 2026-05-11

### Fix - Correct train friendly direction labels across all lines

- Fixed mode-board departure row labeling to resolve route metadata by row `route_id` across all same-mode entries.
- Prevented cross-line label leakage where one train line could inherit another line's friendly direction name.
- Applied the same route-aware label resolution in both coordinator and legacy fallback board aggregation paths.

## [0.10.6] - 2026-05-11

### Feature - Map projection switch with isometric mode

- Added a new `Map Projection` switch in the editor map section:
  - Left: `Normal View`
  - Right: `Isometric View`
- Added `map_projection` card configuration support and runtime camera updates in the map card.
- Isometric mode now applies a pitched/bearing camera (`pitch: 55`, `bearing: -20`) while normal mode uses flat view.
- Updated frontend build marker to `0.10.6`.

## [0.10.5] - 2026-05-11

### Improvement - Direction filter controls and longer bubble dwell time

- Added a segmented direction filter (`All`, `Inbound`, `Outbound`) to the stop departure bubble, keeping a single-column layout for better map readability.
- Added per-row direction chips when both directions are present so mixed lists stay understandable at a glance.
- Increased departure bubble inactivity timeout from 15 seconds to 30 seconds.
- Updated frontend build marker to `0.10.5`.

## [0.10.4] - 2026-05-11

### Fix - Departure bubble duplicate rows at stop level

- Strengthened stop-bubble deduplication to collapse rows by the displayed service identity (`stop_id + route label + direction label + departure timestamp`).
- Prevented duplicate visible entries caused by overlapping board payload rows that differed only in backend trip identifiers.
- Updated frontend build marker to `0.10.4`.

## [0.10.3] - 2026-05-11

### Fix - Departure bubble dedupe and open-sequencing reliability

- Added departure-row deduplication in the bubble merge path so duplicate schedules from overlapping board payloads are shown once.
- Enforced close-first/open-next behavior for stop bubbles with sequence guards to prevent stale async updates and animation race conditions.
- Added a short handoff delay when switching stops so the popout animation reliably replays instead of snapping open when cards overlap.
- Updated frontend build marker to `0.10.3`.

## [0.10.2] - 2026-05-11

### Fix - Departure bubble staged slide animation and marker clearance

- Updated bubble open animation to run in two stages: header slides out from the clicked stop, then the departures body slides down after header motion completes.
- Increased bubble anchor offset so the card no longer overlaps the stop marker when opening.
- Kept responsive and scroll behavior for departure rows while applying staged animation shells.
- Updated frontend build marker to `0.10.2`.

## [0.10.1] - 2026-05-11

### Fix - Departure bubble route direction label

- Updated departure bubble rows to display the route-friendly direction label (for example, `Eastbourne - Petone - Wellington Station - Courtney Place`) instead of the next-stop destination.
- Bubble rows now prefer board payload `direction_label`, with fallback to `destination` only when needed.
- Updated frontend build marker to `0.10.1`.

## [0.10.0] - 2026-05-11

### Feature - Phase 4 departure bubble interaction foundation

- Added clickable stop hubs in the map card so selected stops can open an anchored departure bubble.
- Added animated, anchored departure bubble UI with one-active-bubble behavior, outside-click close, and 15-second inactivity timeout.
- Added frontend departure-board aggregation from mode board `data_url` payloads, merging departures by `stop_id` and sorting chronologically.
- Applied bubble departure filtering rules: keep only future departures, drop services already passed by 1 minute or more, and cap display window to 24 hours.
- Added local-time departure formatting in 24-hour format with countdown text (`xxmin` or `xh ymin`) and stop-level route/destination rows.
- Updated frontend build marker to `0.10.0`.

## [0.9.11] - 2026-05-11

### Fix - Correct live badge pointer direction of travel

- Fixed route-tangent badge heading selection so the marker now chooses whichever route tangent direction is closest to the vehicle's reported bearing.
- This corrects cases where the badge pointer aligned to the route geometry but pointed opposite to the actual direction of travel on bidirectional segments.
- When vehicle bearing is unavailable, the icon still falls back to the route tangent as the best available heading.
- Updated frontend build marker to `0.9.11`.

## [0.9.10] - 2026-05-11

### Fix - Add missing service metadata for Home Assistant

- Added `services.yaml` for the `metlink_explorer.set_live_tracking` service so Home Assistant can load the integration's service definitions without logging `Failed to load services.yaml for integration: metlink_explorer`.
- The service now exposes documented fields for `route_id`, `live_tracking`, and optional `transportation_type` in the Home Assistant service UI.
- Updated frontend build marker to `0.9.10`.

## [0.9.9] - 2026-05-11

### Improvement - Route-tangent badge pointer alignment with vehicle bearing fallback

- **Smart badge heading selection**: Live vehicle badge pointers now align with the route geometry tangent at the vehicle's projected position, providing natural visual alignment with the path.
- **Vehicle bearing fallback**: When tangent direction is ambiguous (both forward and backward directions are equally plausible), the icon uses the vehicle's GTFS-RT bearing attribute to disambiguate and select the correct direction.
- **Graceful degradation**: Falls back to raw vehicle bearing when route geometry is unavailable, ensuring badges always have meaningful direction indicators.
- **Unambiguous direction preference**: When the route geometry provides clear directional guidance, the tangent direction is always preferred over the potentially noisy vehicle bearing.
- **Improved visual accuracy**: Badge pointers now consistently point along the direction of travel relative to the route path, reducing confusion about vehicle movement direction.
- Updated frontend build marker to `0.9.9`.

## [0.9.8] - 2026-05-11

### Fix - GPS-change-driven live vehicle badge rendering

- Replaced blind time-based throttle with GPS snapshot diffing: live badges only re-render when a `device_tracker` entity's position actually changes.
- Switched from per-route slot sources to per-entity MapLibre sources (`live-vehicle-<entity_id>`), so only the individual vehicle that moved triggers a `source.setData()` call.
- Added per-vehicle epsilon guard (0.00001° lat/lon, 0.5° bearing) to suppress `setData` for GPS micro-jitter on stationary vehicles.
- Stale vehicle sources are cleared with an empty FeatureCollection when a vehicle drops off the matched set.
- Removed `_scheduleLiveVehiclesRender`, `_liveRenderTimer`, and `_liveRenderThrottleMs` entirely.
- Removed per-tracker rejection log spam; replaced with a single summary log per render cycle.
- Updated frontend build marker to `0.9.8`.

## [0.9.7] - 2026-05-11

### Change - GPS polling decoupled from card live-tracking toggle

- Reverted backend polling behavior to always fetch vehicle positions and trip updates.
- Card `live_tracking` now controls rendering visibility only.
- This restores the pre-conditional-poll expectation that GPS tracks are collected regardless of card toggle state.
- Updated frontend build marker to `0.9.7`.

## [0.9.6] - 2026-05-11

### Fix - Live tracking skip regression in map card

- Fixed a regression where routes were being skipped for live rendering despite `live_tracking=true` in card config.
- Card-level `live_tracking` now takes precedence for render decisions, with backend feature state used as fallback.
- Improved skip logging to show both card and backend live-tracking values for diagnosis.
- Added `willReadFrequently` canvas context hints for drawing paths that use repeated `getImageData` readbacks.

## [0.9.5] - 2026-05-11

### Fix - Backend authoritative live tracking + frontend route matching

- Added service `metlink_explorer.set_live_tracking` so editor live-tracking toggles persist to integration route config.
- Coordinator polling now stays aligned with saved integration route `live_tracking` values.
- Geometry feature properties now include backend `live_tracking` state so card rendering can use backend-authoritative values.
- Hardened frontend route matching with normalized route key variants (for example `84` <-> `840`, `83` <-> `830`) to improve live vehicle matching.
- Updated frontend build marker to `0.9.5`.

## [0.9.4] - 2026-05-11

### Critical Bug Fix - Editor defaulting live_tracking to false

- Fixed editor defaulting new routes to `live_tracking: false` instead of `true`.
- New routes added via the editor were explicitly saving `false`, overriding the backend default.
- This caused live vehicle tracking to never activate for any new routes added after v0.9.1.
- Live tracking now defaults to **enabled** for all routes, both new and existing.

## [0.9.3] - 2026-05-11

### Hotfix - Frontend build version string for cache-busting

- Updated frontend map card build version string from 0.9.0 to 0.9.2 to properly reflect the running code.
- Console now correctly shows `[MetlinkExplorer] map card script loaded (build 0.9.2)`.
- Improves cache-busting verification when debugging browser caching issues.

## [0.9.2] - 2026-05-11

### Hotfix - Live tracking default for backward compatibility

- Fixed regression in v0.9.1 where existing routes had live_tracking disabled by default.
- Live tracking now defaults to **enabled** for routes without an explicit live_tracking setting.
- This restores backward compatibility so existing users continue to see live vehicles on the map.
- New routes can opt-out of live tracking via the editor checkbox if desired.

## [0.9.1] - 2026-05-10

### Optimization - API efficiency and live tracking configuration

- Reduced vehicle position polling interval from 60s to 30s, aligning with Metlink backend update frequency.
- Vehicle positions and trip updates are now only fetched when a route has **live_tracking enabled**.
- Per-route live_tracking toggle in the card editor controls whether vehicle GPS data is polled for that route.
- Added 304 (Not Modified) support in API client for future cache-aware updates.
- Respects Metlink API guidelines: 10 req/s rate limit; backend updates vehicles ~30s.

## [0.9.0] - 2026-05-10

### Feature - Manual stop selection by route

- Replaced automatic hub rendering with per-route manual selected-stop rendering in the map card editor.
- Added selected-stop management UI for Train, Bus (including School Bus routes), Ferry, and Cable Car route rows.
- Stop picker now removes already selected stops from the available dropdown list and supports per-stop removal.
- Stop labels use the format: Stop <stop_id> :: <stop_name>.
- Train stop ordering now merges and deduplicates timeline directions and rotates to start from Wellington Station when present.
- Bus stop badges now use /metlink_explorer_frontend/bus-stop.png over a black octagon.
- Ferry stop badges are now equilateral triangles and Cable Car stop badges are hexagons.

## [0.8.13] - 2026-05-10

### Feature - Bus hub stop badges

- Bus hub stops now render on the map when "Show Hub Stops" is enabled for a bus route (checkbox already present in editor).
- Bus hub badges are black octagons with a white bus-stop icon (MDI `mdi:bus-stop`).
- Bus hub badges are the same size as train hub badges.
- Bus hub layers are moved to the top of the map layer stack alongside train hub layers.

## [0.8.12] - 2026-05-10

### Fix - Train hub badge orientation

- Train hub badge now renders at 0 degrees so the diamond corners are top, bottom, left, and right.

## [0.8.11] - 2026-05-10

### Fix - Train hub badge rotation

- Removed canvas-side rotation (which was clipping badge corners).
- Applied rotation via MapLibre `icon-rotate: 45` on the train hub layer so the full image is preserved.
- Train badge now displays as the diamond sign oriented correctly.

## [0.8.10] - 2026-05-10

### Fix - Train badge rotation 45 degrees clockwise

- Corrected train hub badge rotation to 45 degrees clockwise.

## [0.8.9] - 2026-05-10

### Fix - Train badge rotation direction

- Corrected train hub badge rotation to counter-clockwise 90 degrees.

## [0.8.8] - 2026-05-10

### Fix - Async await inside forEach

- Converted `forEach` loops in `_renderRoutes` to `for...of` loops so that `await` works correctly inside the async method.
- Resolves `SyntaxError: Unexpected reserved word` thrown at runtime.

## [0.8.7] - 2026-05-10

### Fix - Train hub badge uses real train image

- Train station/stop badge now uses the `train.png` asset image instead of the canvas-drawn glyph.
- Image is rotated 90 degrees clockwise.
- White background pixels are stripped so only the yellow diamond and train are visible.

## [0.8.6] - 2026-05-10

### Fix - Train hub badge emphasis

- Increased the train hub badge size to improve visibility.
- Kept hub/stop layers above live vehicle badges.
- Preserved the shared-location left/right split for train and bus hubs.

## [0.8.5] - 2026-05-10

### Fix - Hub layering and shared-location split

- Hub/stop layers are now moved to the highest map layer so they render above live bus/train badges.
- Shared train+bus hub coordinates now split around the center point with train on the left and bus on the right.

## [0.8.4] - 2026-05-10

### Fix - Hub inference source alignment

- Hub markers are now inferred directly from Geometry sensor `timeline_stops` where `is_hub` is true.
- Removed frontend reliance on alternative hub inference paths to match the Geometry payload contract.

## [0.8.3] - 2026-05-10

### Fix - Route rendering regression and startup blocking IO

- Fixed a hub marker helper signature mismatch that could break route rendering when `Show Hub Stops` was enabled.
- Route re-render cleanup now removes stale hub layers and sources before rebuilding.
- Moved manifest version file read to an executor job during `async_setup` to avoid Home Assistant event-loop blocking warnings.

## [0.8.2] - 2026-05-10

### Fix - Hub stops now render from route geometry

- Added explicit `hub_stops` data to route geometry features so the frontend can render hubs without relying only on nested timeline scans.
- Hub rendering now falls back to `timeline_stops` when needed and logs when no hub stops are detected.
- The editor toggle remains per-route, so MEL, HVL, and bus routes can independently show hub markers.

## [0.8.1] - 2026-05-10

### Feature - Hub stop toggle and rendering foundation

- Added a per-route `Show Hub Stops` toggle in the editor.
- Exposed hub-stop rendering support in the map card using route timeline stop data.
- Added collision helpers so overlapping hub markers can be separated on the map.
- Began mode-specific hub marker support for train and bus-style hub badges.

## [0.8.0] - 2026-05-10

### Feature - Phase 3: Transit Stop Marker System (Infrastructure)

- Added `timeline_stops` data to route GeoJSON features for Phase 3 marker rendering.
- Each route feature now includes stops for both directions (direction 0 and 1) with coordinates, stop names, hub status, and real-time indicators.
- Frontend can now access stop coordinates via the route geometry entity's `geojson` attribute.
- Foundation for upcoming tasks: marker extraction, hub collision detection, and stop clickability.

## [0.7.27] - 2026-05-10

### Improvement - Map-pin direction badge shape

- Redesigned the direction-aware vehicle icon to a map-pin silhouette (round body with pointed tail).
- Kept route label text on a separate non-rotating symbol layer so labels stay upright.
- Adjusted bearing mapping so the pin tip continues to point in the direction of travel.

## [0.7.26] - 2026-05-10

### Feature - Direction-aware vehicle icons

- Vehicle markers now render as a teardrop shape pointing in the direction of travel.
- Bearing is read from the `bearing` attribute of each `device_tracker` entity (supplied by the Metlink GTFS-RT feed).
- The teardrop shape rotates with `icon-rotate: bearing` on a dedicated MapLibre symbol layer.
- Route label text is drawn on a separate non-rotating symbol layer, so the badge text always stays upright regardless of vehicle heading.
- Vehicles with no bearing reported default to pointing north (0°).

## [0.7.25] - 2026-05-10

### Fix - Route line dash patterns

- Rewrote dash pattern definitions to use MapLibre line-width units instead of pixel values.
- Removed the pixel-to-line-width division, which was causing patterns to appear wrong at all zoom levels.
- `dotted` now renders as true circles (1-unit dash closed by round line-cap) with correct spacing.
- All styles (`dashed`, `dash-dot`, `sparse-dotted`, `long-dash`) now have values matched to their descriptors.
- Pattern pitch is now inherently zoom-stable; line thickness control is unchanged.

## [0.7.24] - 2026-05-10

### Fix - Stable route dash pitch

- Normalized route dash patterns to a 16px base so dotted and dashed styles stay visible at all zoom levels.
- Left the editor thickness control unchanged; only the internal dash pitch calculation changed.

## [0.7.23] - 2026-05-10

### Fix - Badge border and dark-text halo

- Removed the extra thick white ring by dropping the legacy hidden circle layer.
- Dark (black) route text now uses a white halo for cleaner contrast.

## [0.7.22] - 2026-05-10

### Fix - Route-locked badge rendering

- Replaced DOM Marker badges with map-native symbol badges generated from canvas images.
- Badge positions are now tied directly to map source coordinates, preventing drift during zoom/pan.
- Retained high-DPI rendering for sharper route label text.

## [0.7.21] - 2026-05-10

### Fix - Marker alignment and sharper route labels

- Switched live badge labels to high-DPI canvas rendering to improve text sharpness.
- Updated map refresh logic so route geometry is not re-rendered on every state update.
- Live state updates now refresh only live markers, reducing flicker and improving marker-to-route alignment stability.

## [0.7.20] - 2026-05-10

### Fix - Visible live route badge labels

- Reworked live vehicle markers into circular badges with centered route labels.
- Increased the route label size substantially so it is readable on the map.
- Bumped the frontend build marker to force HACS and browser caches to fetch the new bundle.

## [0.7.19] - 2026-05-10

### Fix - Frontend cache-bust release

- Bumped the integration version to force Home Assistant and HACS to fetch the latest bundled frontend assets.
- Updated the map card build marker so the console clearly shows the `0.7.19` frontend bundle.

## [0.7.18] - 2026-05-10

### Feature - Route ID text overlay on live markers

- Live vehicle markers now display the route ID (e.g., "83", "WRL") as centered text inside each marker circle.
- Route ID text size automatically scales to match the configured `icon_size` (font size = 40% of icon_size).
- Text color is computed to provide optimal contrast against the marker background color.
- Markers are rendered using MapLibre Marker API to avoid glyph-related rendering issues.

## [0.7.17] - 2026-05-10

### Feature - Configurable live marker icon size

- Added an `Icon Size` slider to the map card editor directly under the `Zoom Level` slider.
- New `icon_size` card config value is now applied to live marker circle radius at render time.
- Default icon size is `33`, matching the previous release behavior until adjusted.

## [0.7.16] - 2026-05-10

### Fix - Route geometry rendering and marker scale tuning

- Fixed route coordinate normalization so valid GeoJSON `longitude,latitude` pairs are no longer incorrectly swapped.
- Restored route line visibility for normal route geometry feeds that already use standard GeoJSON ordering.
- Reduced live marker size by half from the previous release for better map balance.

## [0.7.15] - 2026-05-10

### Fix - Frontend cache-busting and glyph-safe live markers

- Removed live marker text symbol rendering from the bundled map card so styles without `glyphs` no longer throw `text-field` errors.
- Increased live marker circle size by 500 percent for improved visibility.
- Added versioned frontend resource URLs via `?v=<manifest version>` so Home Assistant/browser reloads pull the latest bundled card assets reliably.
- Added a map card startup build marker log to confirm which frontend build is running.

## [0.7.14] - 2026-05-10

### Fix - Live tracking render scheduling and legacy defaults

- Live tracking now defaults to enabled when `live_tracking` is missing from a saved route entry, preserving existing dashboards created before the toggle existed.
- Live marker rendering is deferred until the map is idle if MapLibre still reports the style as unstable.
- This prevents the live-marker pass from being skipped during the initial route render cycle.

## [0.7.13] - 2026-05-09

### Fix - Normalize route geometry coordinates

- Added route geometry coordinate normalization in the bundled map card.
- Obvious reversed lat/lon pairs in LineString and MultiLineString route geometry are now corrected before rendering.
- Tracker GPS data remains unchanged; the fix applies only to route geometry GeoJSON at render time.

## [0.7.12] - 2026-05-09

### Fix - Harden map render pipeline for live tracking

- Added null-safe handling in route geometry parsing when `hass`, `geojson`, or `geojson.features` are missing/malformed.
- Added guarded route rendering with explicit error handling so failures in route line rendering no longer prevent live marker rendering.
- Added style-load skip logs and route render start/end logs to confirm render flow.
- Live marker rendering now continues even when one or more geometry entities are invalid.

## [0.7.11] - 2026-05-09

### Debug - Map lifecycle diagnostics

- Added detailed map card lifecycle logs for `setConfig`, `updated(config/hass)`, `firstUpdated`, `_initMap`, map `load`, and map `error` events.
- Added explicit MapLibre loader success/failure logging, script load timeout diagnostics, and load error handling.
- These diagnostics identify whether live marker rendering is blocked before map initialization or during map style load.

## [0.7.10] - 2026-05-09

### Fix - Live marker matching when geometry is missing

- Updated the bundled map card to fall back to route metadata derived from route entity attributes and entity ID patterns (for example `sensor.bus_83_geometry`) when `geojson` is unavailable.
- Normalized route key matching to be case-insensitive for route IDs and labels.
- This allows live bus/train/ferry markers to render even when route geometry payloads are empty or unavailable.

## [0.7.9] - 2026-05-09

### Debug - Map card load diagnostics

- Added a top-level map card script load log: `[MetlinkExplorer] map card script loaded`.
- Added safe custom element registration with explicit logs for both first registration and already-registered cases.
- This confirms whether Home Assistant is loading the bundled map card resource before diagnosing live-marker matching.

## [0.7.8] - 2026-05-09

### Debug - Live tracking console diagnostics

- Added `console.debug` output to `_renderLiveVehicles` in the bundled map card to trace live tracking pipeline:
  - Logs total device_tracker entity count and current epoch time
  - For each route entry: logs whether `live_tracking` is enabled, routeMeta, and matched vehicle count
  - If no vehicles matched, logs each tracker that passed route matching with its coords/freshness/restored status
- Temporary diagnostic release to identify root cause of live tracking not appearing

## [0.7.7] - 2026-05-09

### Feature - Bundle departure board card into integration

- Added `metlink-departure-board-card.js` to the integration's bundled frontend resources.
- Card is now auto-loaded alongside the map card via `add_extra_js_url` in `async_setup`.
- Users can remove any manually installed `/local/metlink-departure-board-card.js` resource from Lovelace Resources — it is now served automatically from the integration at `/metlink_explorer_frontend/metlink-departure-board-card.js`.

## [0.7.6] - 2026-05-09

### Fix - Bus live route matching from trip_id prefix

- Updated bundled `card` live matching logic to derive route key from `trip_id` prefix (first characters before the first `_`).
- This fixes Metlink route variants where live tracker `route_id` values differ from geometry route identifiers (for example `830` live feed maps to route `83`).
- Added fallback matching using `route_id` and route label for resilience when `trip_id` is missing.

## [0.7.5] - 2026-05-09

### Feature - Route-driven live vehicle tracking on map card

- Reworked bundled `card` + `editor` live tracking from per-vehicle selection to per-route toggles.
- Added `Live Tracking` toggle on each configured route row in the editor.
- Live markers now render route labels (for example `HVL`, `83`) inside the marker with automatic high-contrast text color.
- Marker background color now follows each route's configured line color.
- Live rendering now only uses active tracker positions with recent GTFS-RT timestamps (default 120-second freshness window).
- Vehicle trackers now keep a 2-minute grace period after disappearing from live feed, then drop from map naturally.
- Added live metadata attribute `vehicle_positions_fetched_at` and ensured first coordinator update resets live cache for a fresh post-reload fetch.

## [0.7.4] - 2026-05-09

### Feature - Live vehicle tracking in bundled map card

- Added live vehicle marker rendering to the bundled map card (`card`) for train, bus, and ferry trackers.
- Added new `*_live_entities` config arrays for selecting individual `device_tracker` entities per mode.
- Added live marker styling options in the bundled editor (`editor`): marker color, marker size, and label toggle.
- Route layers and live vehicle layers now render together in a single map update cycle.

## [0.7.3] - 2026-05-09

### Fix - Frontend static path API compatibility

- Fixed `AttributeError: 'HomeAssistantHTTP' object has no attribute 'register_static_path'` introduced in 0.7.2.
- Updated `async_setup` to use `hass.http.async_register_static_paths()` with `StaticPathConfig` dataclass, matching the current Home Assistant HTTP API.

## [0.7.2] - 2026-05-09

### Feature - Bundled Metlink Explorer Map Card

- Added `frontend/` subfolder containing the Metlink Explorer Map Card and its editor JavaScript files.
- Map card and editor are now served directly by Home Assistant at `/metlink_explorer_frontend/` via `hass.http.register_static_path()`.
- Card is automatically registered as a Lovelace frontend resource via `add_extra_js_url()` — no manual resource registration required.
- Added `frontend` to `manifest.json` dependencies.
- Users who previously installed the card manually from `/www/metlink-explorer-map-card/` can delete those files; the integration now handles serving them.
- Updated editor lazy-import URL from `/local/metlink-explorer-map-card/metlink-explorer-editor.js` to `/metlink_explorer_frontend/metlink-explorer-editor.js`.

## [0.7.1] - 2026-05-05

### Fix - Per-route geometry only

- Removed aggregate mode-level route geometry entities from sensor setup.
- Integration now exposes only per-route geometry entities (for example `Train :: KPL Geometry`, `Bus :: 83 Geometry`).
- Prevents recreation of `* :: Route Geometry` entities when users want route-by-route map selection.

## [0.7.0] - 2026-05-05

### Feature - Phase 3: Live vehicle tracking for all transport modes

- **Major feature addition**: Extended live vehicle tracking beyond trains and ferries to include buses and school buses.
- Added Bus (route type 3) to supported device tracker types.
- Added School Bus (route type 712) to supported device tracker types.
- Updated device tracker MODE_ICONS with bus (`mdi:bus`) and school bus (`mdi:school-bus`) icons for map display.
- Live vehicle GPS positions now available for all transport types via GTFS-RT `/gtfs-rt/vehiclepositions` API endpoint.
- Home Assistant map cards can now display live bus and school bus movements alongside trains and ferries.

### Breaking Changes
- None - fully backward compatible. Existing train and ferry tracking remains unchanged.

## [0.6.6] - 2026-05-04

### Change - Single geometry sensor set for map cards

- Removed duplicate `* Geometry Card` entities and reverted to a single geometry sensor set.
- Main geometry sensors now include full-fidelity `geojson` attributes again for direct map-card usage.
- Marked `geojson` as unrecorded on geometry sensors so recorder does not persist large geometry payloads.
- Retained `data_url` JSON file output for file-based geometry access.

## [0.6.5] - 2026-05-04

### Fix - Card-only geometry entities with recorder-safe storage

- Restored full-fidelity `geojson` attributes on new card-only geometry sensors so map cards can render direct entity attributes without track distortion.
- Added aggregate and per-route `* Geometry Card` entities for each configured transport mode.
- Marked `geojson` as unrecorded for card-only entities to avoid recorder database bloat while keeping full `data_url` JSON files available.
- Existing non-card geometry sensors remain file-first and lightweight.

## [0.6.4] - 2026-05-04

### Fix - Recorder-safe geometry attributes

- Added adaptive GeoJSON preview generation for geometry sensor attributes to keep payloads under recorder-safe size limits.
- Geometry attributes now include a simplified coordinate preview plus truncation metadata fields.
- Full-resolution geometry remains available through `data_url` JSON payload files.

## [0.6.3] - 2026-05-04

### Maintenance - Release metadata alignment

- Bumped integration release metadata to 0.6.3 across project files.
- No functional transport-data behavior changes in this release.

## [0.6.2] - 2026-05-04

### Fix - Restore geojson attribute to geometry sensors

- `geojson` attribute (GeoJSON FeatureCollection) restored to both the aggregate mode geometry sensor and the per-route line geometry sensor.
- The 0.6.0 refactor moved geometry to JSON files only, breaking any map card that reads `geojson` directly from sensor attributes.
- Geometry data is now available in both the `geojson` attribute (for direct card use) and the `data_url` JSON file (for programmatic/file-based access).
- Note: if a route's geometry payload is very large, the HA recorder 16 kB warning may recur for that entity. Use `data_url` for those cases.

## [0.6.1] - 2026-05-04

### Fix - Suppress expected missing-direction log noise

- "No stop pattern found for route X direction Y" downgraded from `ERROR` to `DEBUG` with a descriptive note that routes like 14 (shared QDF/MIF) and 8 do not operate symmetrically in both directions.
- Return value changed from `{"error": "No stop pattern found"}` to `{"error": None}` so sensors do not surface a spurious error state.
- "Getting route timeline for card display", "Found stop pattern with N stops", "Processing N stops in pattern", and "Built timeline with N stops" downgraded from `INFO` to `DEBUG` — these fired on every 60-second coordinator poll and contributed to the 200-messages/minute logging flood.

## [0.6.0] - 2026-05-04

### Feature - Route geometry sensors for all transport modes

- Added GTFS shapes geometry coordinators and sensors for Ferry, Bus, School Bus, and Cable Car modes — matching the existing Train geometry sensor pattern.
- Per-route geometry sensors are created for all configured routes in every mode (e.g. `Ferry :: QDF Geometry`, `Bus :: 83 Geometry`).
- Aggregate mode geometry sensors expose a full GeoJSON FeatureCollection per mode.
- Geometry refresh uses the same weekly TTL as Train, appropriate for GTFS static shape data.

### Fix - HA recorder 16 kB attribute limit exceeded

- Large payloads (departures boards, route timelines, route geometry) are now written to JSON files under `/config/www/metlink_explorer/` on every coordinator update.
- Sensor `extra_state_attributes` now contains only lightweight summary fields and a `data_url` pointing to the `/local/metlink_explorer/...` file path.
- This eliminates all "State attributes exceed maximum size of 16384 bytes" recorder warnings.

### Fix - Redundant live GTFS-RT API calls

- Added a 30-second shared TTL cache for `/gtfs-rt/vehiclepositions` and `/gtfs-rt/tripupdates` on the `MetlinkApiClient` instance.
- All route coordinators share the same client, so the live feed is downloaded once per 30 seconds regardless of how many routes are configured (previously downloaded once per route per polling cycle).

### Fix - Stop predictions circuit breaker

- `get_stop_predictions()` now tracks per-stop consecutive failures.
- After 5 consecutive failures (e.g. HTTP 502) a stop is skipped for 15 minutes before being retried.
- A single `WARNING` is logged when the circuit opens; subsequent skips log at `DEBUG` only.
- Eliminates the 200-message/minute logging flood from repeated stop prediction failures.

### Fix - DOMAIN NameError in device_tracker platform

- Added missing `DOMAIN` import to `device_tracker.py` — resolves the `NameError: name 'DOMAIN' is not defined` traceback on startup.

### Fix - Noisy log levels for expected data gaps

- "No trips found for route X direction Y" downgraded from `ERROR` to `DEBUG`.
- "No stop times found for trip ..." downgraded from `WARNING` to `DEBUG` with a note that dated/exception trip IDs are expected to sometimes return empty.

### Fix - Departures board double-compute per update cycle

- `_build_departures()` now runs once per coordinator update (in `_async_write_payload`) and caches the departure count.
- `native_value` reads the cached count; `extra_state_attributes` reads the cached summary — eliminating the duplicate expensive aggregation call.

### Change - Remove SensorStateClass.MEASUREMENT from all sensors

- Removed `SensorStateClass.MEASUREMENT` from route, direction, and board sensors.
- HA will no longer attempt to track long-term statistics for these entities, resolving the unit-of-measurement mismatch errors in the recorder.
- Existing stale statistics can be cleared from Developer Tools → Statistics in the HA UI.

## [0.5.4] - 2026-04-09

### Fix - Distinguish MIF and QDF trips in combined ferry board output

- Added per-trip ferry service labeling for shared route_id services (MIF/QDF) during timetable row generation.
- Board aggregation now prefers row-level service labels so combined sensors can list both services distinctly in chronological order.
- Added service-label context fields to timetable rows to improve downstream card rendering and debugging.

## [0.5.3] - 2026-04-09

### Fix - 24h lookahead departures for bus and ferry boards

- Route coordinators now build board timetable rows from both today and tomorrow service dates, with row deduplication.
- Departures board ETA calculations are now service-date aware, so tomorrow rows are treated as upcoming instead of dropped.
- Improves visibility for routes with low frequency or no remaining same-day departures.

## [0.5.2] - 2026-04-09

### Fix - Bus and ferry departures board row filtering

- Added non-train fallback to `arrival_time` when `departure_time` is missing in stop-time rows.
- Restricted terminal-stop exclusion to train mode so non-train rows are not over-pruned.
- Relaxed service-date active exception filtering for non-train modes (explicit removals still apply).
- Updated departures ETA parsing to use GTFS service-time seconds (including 24+ hour values) for robust upcoming-row detection.

## [0.5.1] - 2026-04-09

### Feature - Physical offset lanes for overlapping train geometries

- Added overlap-aware coordinate offset processing for train route GeoJSON output.
- Offsets are applied only where routes share the same coordinates; single-line sections remain on native track coordinates.
- Implemented lane-ordering rules for MEL/HVL/WRL/KPL/JVL overlap cases, including MEL-missing and KPL-missing fallback behavior.

## [0.5.0] - 2026-04-09

### Refactor - Canonical mode grouping and route ownership

- Added shared mode-registry helpers for normalized transportation-type handling, deterministic mode leaders, and merged route ownership across entries.
- Refactored setup, sensor, select, and device-tracker platforms to use the shared helpers instead of duplicating mode matching logic.
- Consolidation and runtime route enumeration now use consistent route normalization to reduce restored-only ghost entities.

### Refactor - Route download and geometry cache behavior

- Added cached trips index by route to avoid repeated full `/gtfs/trips` downloads per route update cycle.
- Added per-trip stop-times cache to reduce repeated `/gtfs/stop_times` calls across timetable and geometry workflows.
- Reworked route-geometry caching to use short negative caching (5 minutes) for missing geometry, preventing week-long stale "no geometry" states.

## [0.4.16] - 2026-04-09

### Fix - Train geometry entities always created when coordinator exists

- Train geometry sensor creation is no longer gated by mode-leader checks.
- Per-line and aggregate train geometry entities now initialize whenever a train entry has a geometry coordinator.
- Mode-leader detection now normalizes transportation type comparison as integers to avoid string/int mismatch edge cases.

## [0.4.15] - 2026-04-09

### Fix - Train startup route consolidation and coordinator initialization

- Setup now unions routes across all matching entries (same API key + mode) before leader initialization.
- Leader entry route data is updated up-front so route coordinators are created for every installed train route in the same startup cycle.
- Prevents non-primary train routes from remaining as restored-only entities without live data after reload/startup.

## [0.4.14] - 2026-04-09

### Fix - Train route availability and per-line geometry entities

- Route selection filtering now scopes configured-route checks to the same API key and transportation mode, preventing unrelated entries from hiding valid train routes.
- Train per-line geometry sensors are now created for all configured train routes, then enriched with any additional routes present in geometry features.
- This ensures line entities like KVL and MEL can exist whenever those train routes are installed, even before geometry features fully populate.

## [0.4.13] - 2026-04-09

### Fix - Train geometry route enumeration from installed routes

- Train geometry collection now uses the union of installed train routes across matching config entries (same API key + mode).
- Geometry route scope remains installed-routes-only and no longer expands to all GTFS train routes.
- Per-line geometry sensors now enumerate from geometry feature payloads to reflect installed route coverage.

## [0.4.12] - 2026-04-09

### Fix - GTFS shapes collection uses required shape_id query

- Updated GTFS shapes collection to query `/gtfs/shapes?shape_id=...` per shape, matching API requirements.
- Added URL-encoding for shape IDs and per-shape cache entries for static geometry reuse.
- Resolved empty route-geometry feature payloads caused by invalid bulk shapes requests.

## [0.4.11] - 2026-04-09

### Fix - Route geometry fallback when GTFS shapes are missing

- Added route-geometry fallback generation from stop-pattern coordinates when GTFS shape data is unavailable.
- Train route geometry sensors now populate GeoJSON features more reliably for map overlays.

## [0.4.10] - 2026-04-09

### Feature - Per-route train geometry sensors for custom map coloring

- Added per-route train geometry sensors so each configured train line can be styled independently on map overlays.
- Added default color hints for common train line abbreviations (for example HVL, KPL, JVL, MEL, WRL).
- Retained the combined train geometry sensor while adding route-specific geometry outputs for custom map-card styling.

## [0.4.9] - 2026-04-09

### Feature - Train route geometry for map overlays

- Added GTFS shapes support and cached route geometry extraction as GeoJSON features.
- Added a train route geometry coordinator with weekly refresh cadence.
- Added a train route geometry sensor exposing GeoJSON feature collections for custom map overlays.

## [0.4.8] - 2026-04-09

### Feature - Weekly train GTFS static cache

- Added a train-specific static GTFS cache policy with a 7-day TTL.
- Train static datasets now cache weekly for routes, stops, calendar dates, stop patterns, and timetable base rows.
- Realtime feeds remain unchanged and continue polling live.

## [0.4.7] - 2026-04-09

### Feature - Live vehicle trackers for map cards

- Added `device_tracker` entities for live Ferry vehicle positions using GTFS-RT vehicle position data.
- Extended live vehicle trackers to Train mode so train vehicles can also be shown on map cards.
- Tracker entities are created dynamically as vehicles appear and include live metadata like route, trip, bearing, speed, and timestamp.

## [0.4.6] - 2026-04-09

### Fix - Departure board terminal-stop handling

- Departure board row generation now uses `departure_time` only (not `arrival_time` fallback).
- Excludes terminal-stop rows from departure board payloads to prevent entries like "Wellington Station -> Wellington Station".
- Improves train board output where terminating services previously appeared as departures from their final stop.

## [0.4.5] - 2026-04-09

### Fix - Departures board update cycle behavior

- Adjusted board ETA handling so past departures are no longer wrapped to next-day countdowns.
- Mode board rows now include upcoming departures only, preventing stale services from appearing as large future ETAs (for example 18h+).
- This improves real-world dashboard behavior for bus/ferry/train board cards that display "Departs ... in ..." values.

## [0.4.4] - 2026-04-08

### Change - Remove legacy direction sensors

- Removed creation of legacy fixed-direction sensors for each route.
- New installs now create route-centric entities only for route data display.
- Keeps the streamlined model focused on the `... :: Route` sensor flow.

## [0.4.3] - 2026-04-08

### Feature - Single integration entry per transport mode

- Updated setup and config flow to support one config entry per transportation mode (for example, a single Ferry entry containing multiple selected ferry routes).
- New routes selected for an existing mode are now appended to that existing mode entry instead of creating separate entries.
- Added auto-consolidation during setup for legacy duplicate entries with the same API key and transport mode.
  - Routes are merged into a single leader entry.
  - Duplicate mode entries are removed after successful merge.

### Compatibility

- Legacy single-route entry data remains supported.
- Route and direction entities remain available, now grouped under one mode entry when consolidated.

## [0.4.2] - 2026-04-08

### Fix - Timetable board accuracy and provenance

- Reworked board-row generation to build departures from GTFS static data (`trips` + `stop_times`) for the selected service date.
- Added service-date filtering using `calendar_dates` exception rules before row generation.
- Destination is now derived from each trip's final stop instead of direction-label fallback.
- Board rows now represent one trip-stop event per row and are sorted chronologically by service-time.
- Added GTFS-RT trip updates overlay so realtime departures replace scheduled values when available.

### New debug fields per board row

- `trip_id`
- `service_id`
- `service_date`
- `stop_sequence`
- `scheduled_departure_time`
- `debug_source`

### Notes

- This update is intended to align board entity output with timetable-style expectations more closely.
- Existing entities and dashboards remain compatible.

## [0.4.1] - 2026-04-07

### Feature - Aggregate departures board entities

- Added a transportation-mode board sensor that aggregates upcoming departures across all configured routes of the same mode.
- Board sensors are created for configured modes (for example Ferry, Bus, Train) and expose normalized departure records for dashboard filtering.
- Added `departures` payload rows with route, direction, stop, destination, departure time, ETA, and realtime/source metadata.
- Added sorting and ETA normalization so board rows can be rendered consistently for stop-level cards.

### Compatibility

- Existing route-centric sensors and legacy direction compatibility sensors remain available.
- New board entities are additive and do not replace existing route entities.

## [0.4.0] - 2026-04-07

### Major Architecture Update - Route-centric design with migration compatibility

- Added a route-centric update model with one shared coordinator per configured route.
- Added a new primary route sensor entity to represent both travel directions in one place.
- Added a direction `select` entity so users can switch the active direction at runtime from cards/UI.
- Preserved legacy direction sensor unique IDs (`metlink_explorer_<route_id>_0` and `_1`) where possible for dashboard compatibility.
- Route data for both directions is now fetched and processed under the same route coordinator cycle.

### Config and setup improvements

- Added default config entry options for route-centric behavior:
  - `active_direction` defaulting to direction `0`
  - `legacy_direction_entities` defaulting to `true`
- Removed duplicated route option sorting method from the config flow to avoid accidental logic shadowing.

### Notes

- Existing installations should continue to see legacy direction entities while gaining the new route-centric entities.
- This release lays the foundation for future API call and Recorder overhead reduction work.

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
