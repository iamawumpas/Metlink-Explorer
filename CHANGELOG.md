# Changelog

All notable changes to the Metlink Explorer Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.9.0] - 2026-10-28

### Changed - Settings follow your Home Assistant user

- Card choices are saved per Home Assistant user instead of per browser, so they follow that user across devices. Existing browser-saved choices are imported the first time that user opens a card.

## [2.8.10] - 2026-10-28

### Changed - Vehicle positions refresh every 10 seconds

- Why: Metlink updates its vehicle feed every 4 to 8 seconds, but the map only asked for it every 30, so positions were on average about 15 seconds older than they needed to be.
- Vehicle positions are now fetched every 10 seconds while a card is open. Trip updates (30 seconds) and alerts (3 minutes) are unchanged.
- Each fetch is about 50 KB and took about 0.14 seconds when tested. Nothing is fetched when no card is open.
- Some vehicles still show positions a minute or two old. That delay comes from Metlink, not from this integration.

## [2.8.9] - 2026-10-26

### Added - Starting zoom setting

- Why: the zoom the map opens at was fixed.
- A "Starting zoom" number box (with up and down arrows) in the Map group of the Filters panel, from 8 to 19, default 14. The map opens at this zoom, centred on your home. The choice is remembered in your browser and takes effect the next time the map opens. In YAML it is `start_zoom`.
- Without a home location the map opens on central Wellington at this zoom.

## [2.8.8] - 2026-10-26

### Changed - Map opens centred on your home

- Why: the map opened on a wide harbour view, which was too far out to be useful.
- The map now starts at zoom 14 centred on your Home Assistant home zone (or the home location in your settings). If no home location is set, it opens on central Wellington at zoom 12 as before.
- The map no longer jumps to fit the selected routes when it opens, so the home view stays. Pan and zoom as usual.

## [2.8.7] - 2026-10-26

### Fixed - Departure board no longer repeats the time

- Why: for a departure more than an hour away, the board showed the same clock time twice in one row.
- The scheduled time is shown once. If the live time differs (a delay or early running), the live time still appears next to it.

### Changed - Map opens on the Wellington harbour view

- Why: the map opened centred on the city, with the Hutt and Eastbourne side of the harbour cut off.
- The starting view is now centred on the harbour at the same zoom as before, so the city, Eastbourne and the Hutt Valley are all in view. Panning and zooming are unchanged.

## [2.8.6] - 2026-10-26

### Removed - Legacy version 1 files

- Why: the version 1 integration and its troubleshooting material were no longer needed after the version 2 rebuild.
- Removed the archived version 1 integration, its old cards and marker images, and troubleshooting documents for the retired implementation. The active version 2 integration, its logo and current tests remain.

## [2.8.5] - 2026-10-26

### Added - `records` option on the departure board

- Why: to cap how many departures each stop shows.
- `records: 3` in the card YAML shows only the next 3 departures for each stop. Leave it out to show all that were fetched (`limit`, default 10). If `records` is larger than `limit`, more are fetched to match.

## [2.8.4] - 2026-10-26

### Changed - Departure board is grouped by stop

- Why: grouping by route split one stop's departures across many small lists.
- Each stop now has its own heading (stop name, its colour, and the Towards choice if one is set), sorted alphabetically like the chips. Under it are all of that stop's departures in time order, each row showing the route badge, destination, time and countdown. The Towards filter still sets the direction.
- Every stop shows up to `limit` departures (default 10). The `per_route` setting is gone.
- Route badge colours behave as before (map colour, or click to choose).

## [2.8.3] - 2026-10-26

### Changed - Departures after midnight show the day

- Why: departures for tomorrow or later looked the same as today's.
- Any departure not on today's date now shows the short day name before the time, for example "Tue 08:43 AM". Today's stay as plain times. This applies to the departure board and to the stop popups on the map.

## [2.8.2] - 2026-10-26

### Changed - Departure board route colours follow the map

- Why: the same route could be one colour on the map and another on the board.
- A route you have picked on the map card now uses that chip colour on the board. For any other route, click its badge on the board to choose a colour (remembered in your browser). Until you do, it keeps the Metlink colour.
- If you use a map card with a YAML `id`, set `map_id` with the same value on the board so it reads that map's colours.

### Fixed - Departure board height in a Sections dashboard

- Why: setting `height` in YAML had no visible effect in a Sections view, because the card did not declare its grid sizing and the grid kept its own row height.
- The card now asks the grid for automatic row height (as the map card does) and is a block element, so `height: 500` (pixels) or `height: 60vh` is honoured.

## [2.8.1] - 2026-10-26

### Fixed - Departure board scrolls, can be resized, and delays are readable

- Why: with no `height` set the card just grew, so there was never a scrollbar. The "+2 min" delay was hard to read on the orange bars.
- The card now stops growing at 70% of the screen height and the list scrolls inside it (vertical scrollbar only).
- Drag the bottom-right corner of the card to set its height by hand. The size is remembered in your browser. A YAML `height` still overrides this.
- Delay and early notes sit on a dark pill, so they read on any stop colour.

## [2.8.0] - 2026-10-26

### Changed - Departure board shows several stops, grouped by route

- Why: the board could show only one stop, in one long list.
- Pick several stops (up to 8). Each is a chip, sorted alphabetically, with a colour you can change by clicking the chip. Each stop has its own "Towards" filter.
- Departures are grouped by route and destination, soonest group first. Under each group the next 3 departures are shown (`per_route` in YAML), each on a bar that fades from black on the left to the stop's colour on the right.
- Each stop still fetches 10 departures (`limit`). A stop that fails does not hide the others.
- New YAML `height` (pixels, or any CSS size such as `40vh`). The list scrolls vertically inside it and the search and chips stay in view.
- A stop saved by the old single-stop board is carried over.

## [2.7.1] - 2026-10-26

### Added - Data sources are credited on the map

- Why: the Metlink timetable and live data, and the AISStream ship positions, were not acknowledged.
- The usual attribution strip at the bottom right of the map now credits the data sources alongside the map tile credit: "Metlink data © Greater Wellington Regional Council (CC BY 4.0) · Live AIS via aisstream.io, provided without warranty", with links.
- Metlink publishes its open data under the Creative Commons Attribution 4.0 licence, which requires crediting the Greater Wellington Regional Council. AISStream publishes no formal terms or attribution rule, so the wording follows the one other sites use for it.

## [2.7.0] - 2026-10-26

### Added - Home is shown on the map

- Why: there was no way to see where home is in relation to stops and vehicles.
- A 🏠 marker shows the Home Assistant home zone, with a faint circle for the zone's radius. It uses the location of the `zone.home` zone and falls back to the location set in Home Assistant's general settings. If you move the zone, the marker follows.

## [2.6.11] - 2026-10-26

### Added - Alerts are colour coded by severity

- Why: every alert looked the same, so a cancelled service was no more noticeable than a minor notice.
- Metlink gives each alert a severity. Severe alerts have a red edge and a "Severe" tag, warnings are orange with a "Warning" tag, and information notices are blue with an "Info" tag. If Metlink gives no severity, the alert's effect (for example "no service") is used, and otherwise it stays the usual amber.
- The most severe alerts are listed first, and the alerts line at the top of the map takes the colour of the worst one.

## [2.6.10] - 2026-10-26

### Changed - Filters panel sliders fill the row

- Why: the sliders were short and left empty space in the panel.
- The stop size slider now stretches to fill the rest of the line beside Show stops.
- The map type dropdown is renamed Style, and the darken slider now sits on the same line and fills the remaining space.

## [2.6.9] - 2026-10-26

### Changed - Stop size sits beside Show stops

- Why: the stop settings took more lines than they needed to.
- The stop size slider is now on the same line as "Show stops", and is shorter so both fit in the panel. Stop colour and stop bubbles are on the line below.

## [2.6.8] - 2026-10-26

### Changed - Stop bubbles setting sits beside stop colour

- Why: the two stop settings that take the least room were on separate lines.
- "Stop bubbles" now sits on the same line as "Stop colour" in the filters panel. On a very narrow screen it wraps to the next line.

## [2.6.7] - 2026-10-26

### Changed - Narrower buttons on the map

- Why: the buttons down the right edge were a little wider than they needed to be.
- They are now 94 pixels wide instead of 110, which still fits "Cable car". On a route chip there is a gap between the route number and the ✕.

## [2.6.6] - 2026-10-26

### Changed - Border around the filters panel

- Why: the panel blended into the map and was hard to pick out.
- It now has a 2 pixel border in the theme's accent colour, with rounded corners.

## [2.6.5] - 2026-10-26

### Changed - Filter options are grouped

- Why: the options in the filters panel were in no particular order.
- The route search is at the top. Below it, a "Map" group holds the map type and darken slider, and a "Stops" group holds show stops, stop colour, stop size and stop bubbles.

## [2.6.4] - 2026-10-26

### Changed - Picked route chips are sorted by number

- Why: chips appeared in the order you added them, so the row looked jumbled.
- They now always show in number order (2, 83, 84, 130, 887, then letters such as N1), whatever order you picked them in. Colours stay with each route.

## [2.6.3] - 2026-10-26

### Fixed - Bus on with routes picked now tracks every bus

- Why: picking a bus route switched off live tracking for all the other buses, even with the Bus button on.
- With Bus on, every bus is tracked live. Lines and stops are drawn only for the bus routes you picked, so the map stays uncluttered. Alerts also still follow your picked routes only.

## [2.6.2] - 2026-10-26

### Fixed - The filters panel is only as tall as its contents

- Why: the panel stretched down the whole height of the map even when it had little in it.
- It now fits its contents, and scrolls only if it would be taller than the map.

## [2.6.1] - 2026-10-26

### Changed - Buttons on the map are all the same width

- Why: the Filters button, mode buttons and route chips were different widths, so the column down the right edge looked ragged.
- They are now all the same width and line up. On a route chip the ✕ sits at the right edge with the route number centred.

## [2.6.0] - 2026-10-26

### Changed - Filters moved into a slide-in panel so the map is bigger

- Why: the Filters area sat above the map and took a lot of room, especially with several routes picked.
- The map now starts at the top of the card. A "⚙ Filters" button on the right edge opens a panel over the right side of the map, holding stops, map type, stop bubbles, darken, stop colour and size, and the bus route search. Nothing on the map moves when it opens. Close it with the × button; tapping the map does not close it, so you can change settings while watching the map.
- The Bus, Train, Ferry and Cable car buttons, and the chips for your picked bus routes, stay on the map at the right edge all the time. Tap a picked route's name to change its colour, as before.
- The alert line stays centred at the top and now leaves room for the buttons.

## [2.5.4] - 2026-10-26

### Fixed - Train, ferry and cable car stops now show

- Why: every kind of stop only appeared once you zoomed in close, and that was too far in to see station stops on a view of the whole region. Train stops looked as if they were missing.
- With Train, Ferry or Cable car on, their stops now show at every zoom level. Bus stops still need zooming in, because there are thousands of them.

## [2.5.3] - 2026-10-26

### Changed - The map is limited to the Wellington region

- Why: you could zoom out and drag the map away from the area the services cover.
- The map can no longer be zoomed out past, or dragged beyond, the region from Kapiti to the Wairarapa. The limit follows the card size, so a bigger card can show a little more around the edge.

## [2.5.2] - 2026-10-26

### Changed - The map fills the screen height

- Why: the map had a fixed height, so on a large display it stopped short of the bottom of the screen.
- The map now stretches from its top edge to the bottom of the screen. It is measured when the page loads and when the screen turns between portrait and landscape, so scrolling never changes its size.
- Setting `height:` in the card YAML still gives a fixed height. The map is never shorter than 320 pixels.

## [2.5.1] - 2026-10-25

### Fixed - Long alert lists now scroll

- Why: when there were more alerts than fitted in the box, the extra ones ran off the bottom of the map and could not be reached.
- The alert box is now limited to the height of the map and gets a vertical scrollbar when it needs one. Scrolling it no longer scrolls the page behind it.

## [2.5.0] - 2026-10-25

### Changed - Alerts are now one line over the top of the map

- Why: the alert list sat above the map and took up a lot of room.
- All alerts are now a single line over the top of the map: "⚠ N alerts may affect your travel". It takes no extra space and shows nothing when there are no alerts.
- Tap it to open the full text of every alert. Each alert shows a chip in the colour of the route it affects.
- It closes when you tap the map or anywhere outside it, or with the × button.
- The old banner for replacement bus services was removed. Those alerts are in the list like the others.

## [2.4.1] - 2026-10-25

### Fixed - Melling line drawn above the other routes

- Why: the Melling (MEL) line is short and could be hidden underneath longer routes.
- Its line is now drawn on top of every other route.

## [2.4.0] - 2026-10-25

### Changed - Mode buttons now show every route of that mode, whatever bus routes are picked

- Why: picking a bus route hid everything else, even with Train, Ferry or Cable car switched on.
- With Train, Ferry or Cable car on, all their routes, stops, alerts and live vehicles show. Picked bus routes show as well. With Bus on and no routes picked, all buses show. With Bus on and routes picked, only those buses show.
- This needs two live subscriptions at once (picked routes, plus the active modes). The card merges them.
- The search box now only lists bus routes, and reads "Add specific bus routes. Search by number or name…".
- Trains are currently replaced by buses, so Train shows the lines and alerts but probably no live trains.

## [2.3.5] - 2026-10-25

### Changed - Live vehicle icons: white border and higher-contrast text

- Why: the vehicle icons already used the route colour in 2.3.0, but the border changed with the colour and the black or white text was a rough guess that was hard to read on mid colours such as green and red.
- Every live vehicle badge (bus, train, ferry and cable car) now has the same white border, with a thin dark ring so a white ferry badge still shows on a light map. The fill is the route colour you picked, or the default for that mode (buses slate, each train line its own colour, ferry white, cable car black).
- Text on the badge, route chips and stop bubble rows is now whichever of black or white has the higher contrast with the colour. All the default colours now reach at least 5:1 (the accessibility minimum is 4.5:1).

## [2.3.4] - 2026-10-25

### Changed - Route chips take the route colour

- Why: the small colour box inside each route chip was fiddly and hard to read against the chip.
- The whole chip is now filled with the route colour, with black or white text, whichever contrasts better. Click the route name to change the colour. The ✕ still removes the route.

## [2.3.3] - 2026-10-25

### Fixed - Departure times line up in the stop bubble

- Why: the "late" label sat inside the time column, so times and "min" labels didn't line up between rows.
- Times are now right-aligned in their own column, and the "late" label has a column of its own, so every "min" and every label lines up.

## [2.3.2] - 2026-10-25

### Changed - Late departures blink red

- Why: "(late)" in the same colour as the row was easy to miss.
- A delayed departure now shows a red "late" label that blinks. It sits in a small white pill, because red text would disappear on a red or orange route row.
- The blinking stops for anyone whose device is set to reduce motion.

## [2.3.1] - 2026-10-25

### Changed - Tidier stop bubbles

- Why: with the coloured rows, the bubble looked lopsided, and the coloured bar beside the stop name no longer meant anything.
- The stop name is centred and the departure rows fill the bubble's full width, so the left and right margins match.
- The coloured bar next to the stop name is gone.

## [2.3.0] - 2026-10-25

### Added - Pick a colour for each route

- Why: Metlink's own route colours are often the same or hard to see, so selected routes were hard to tell apart.
- Each route you add gets the next free colour from red, orange, yellow, green, blue, indigo, violet (cycling after seven). The swatch on the route chip opens a colour picker. The choice is saved per card, and `routes:` in the YAML can carry a `color`.
- The colour is used for that route's line on the map, its live vehicle icons and arrows, the rows in a stop's departure bubble, and the bubble's heading bar. Text on a colour switches between black and white so it stays readable.
- Routes you haven't picked: buses are one fixed slate colour. Each train line has its own colour from the same seven (KPL red, HVL orange, JVL yellow, MEL green, WRL blue). Ferry is white and cable car is black.
- Train, ferry and cable car lines are drawn dashed. Every line now has a thin outline so white and black lines stay visible on any map.
- Changed: a line with a service alert is now dotted instead of dashed, because dashed now means "not a bus".
- Changed: departure rows in the stop bubble are filled with the route colour instead of a route badge. Delayed departures say "(late)" instead of using red text.
- The route colours supplied by Metlink are no longer used.

## [2.2.6] - 2026-10-25

### Added - Light or dark stop bubbles, with a route-coloured heading

- Why: the white popup that appears when you tap a stop clashed with dark dashboards, and had no link to the routes serving the stop.
- Filters has a new "Stop bubbles" setting, Light or Dark. It's remembered per card, and `popup_theme: dark` works in the YAML. Light stays the default.
- The stop name in the bubble now has an accent bar in the colour of the route with the next departure (grey if the route has no colour).
- Not included: making route colours clearly different from each other, or letting you pick them. That belongs with the route-colour patch, since many Metlink routes share colours.

## [2.2.5] - 2026-10-25

### Added - Choose the map from the card settings

- Why: the card only had street and (until 2.2.4) light maps, and you wanted more choices without API keys.
- Filters has a new "Map" dropdown: Street, Satellite and Topographic. The choice is remembered per card, and `basemap: satellite` (or `topo`) works in the YAML. A previously saved "light" choice falls back to Street.
- All three are Esri tile services that load without an API key. I fetched a Wellington tile from each and checked the picture. They are sharp to at least zoom 19.
- Left out on purpose: OpenStreetMap now serves an "Access blocked" tile to apps like this, and CARTO (the old Voyager and Positron maps) serves "API KEY REQUIRED".

## [2.2.4] - 2026-10-25

### Removed - Light map toggle

- Why: the new Darken map slider covers what the toggle was for.
- The map always uses the street basemap unless the card YAML sets `basemap: light`. A previously saved "light" choice is ignored.

## [2.2.3] - 2026-10-25

### Added - Configurable stop colour and size

- Why: the new orange stops suit some maps and not others, and the right size depends on the screen.
- Filters now has a "Stop colour" picker and a "Stop size" slider (3-20). Changes apply to the stops on the map straight away and are remembered per card.
- They can also be set in the card YAML with `stop_color: "#ff0000"` and `stop_size: 12`.
- The default is still amber at size 10.

## [2.2.2] - 2026-10-25

### Changed - School buses merged into buses, bigger stops, darken-map slider

- Why: school buses were a separate checkbox that hid routes and vehicles, stops were hard to see and tap, and the map could not be dimmed so the routes stood out.
- The School buses checkbox is gone. School routes and vehicles now appear as ordinary buses.
- Stop markers are twice the size and orange/yellow.
- New "Darken map" slider (0-80%) dims only the map tiles, not routes, stops or vehicle icons. It is remembered per card.

## [2.2.1] - 2026-10-24

### Changed - Map card takes the full width of a dashboard section

- Why: in Sections view the map card could not be widened, because it did not tell Home Assistant what size it wanted and was locked to the default width.
- The map card now asks for the full 12-column width of its section by default, with automatic height, and can be resized down to 3 columns by dragging its handle while editing.
- Not included: filling only the space left by other cards. A card cannot see its neighbours and Home Assistant has no "fill the remaining space" setting, so another card in the same section wraps onto its own row unless you shrink the map by hand.
- Only applies to Sections view.

## [2.2.0] - 2026-10-24

### Added - Service alerts, replacement notices and cancelled trips on the map

- Why: with the Train button on, the map showed nothing because the trains are currently replaced by buses, and Metlink's timetable counts those buses as buses. You asked for the map to say so, and to show other alerts and cancellations too.
- A banner above the map lists the active service alerts for the buttons you have switched on. If you pick routes, it shows alerts for those routes instead. Network-wide alerts are included. Alerts that mention replacement or "replaced by" buses are pinned in orange above the list.
- Rail-replacement buses stay as buses, as you asked. The pinned notice explains why trains are missing.
- A selected route with an alert is drawn dashed, and hovering over it shows the alert headline.
- Tapping a stop also shows any alert for that stop.
- A vehicle on a cancelled trip is faded and labelled "(cancelled trip)".
- Only alerts that are active right now are shown.
- New `subscribe_alerts` websocket subscription, and the `alerts` command now accepts `modes`. Alerts include the matched routes, the modes they affect and a `replacement` flag; vehicles include `canceled`.
- Not yet confirmed: this has not run against Metlink's real alert data in Home Assistant. Alerts may use route ids that differ from the timetable, so I match them by id, short name and trip. The replacement notice is a text match on the alert wording, so an unusual phrase could be missed. Cancelled trips often have no vehicle on the road, so a faded vehicle may be rare.

## [2.1.8] - 2026-10-24

### Fix - Cards disappeared from the picker a moment after the page loaded

- What happened: the 2.1.7 console log showed the map card registering correctly (`registered = true`), then the element being missing about a second later (`element missing after 1000 ms, registering again`). Something in the page discards the definition shortly after load, so the card picker and editor found nothing and reported "Custom element not found". Other cards survive because they load later, as dashboard resources, while ours load early with the integration. This is my explanation from the log; I have not proven what removes the definition.
- Both cards now check every 250 ms for the first minute and register themselves again whenever the element is missing, so the gap is much shorter than the 1 s wait in 2.1.7. A console warning is written each time this happens.
- The departure board card gets the same protection, although it is not in use yet.
- Not yet confirmed: that the picker now lists the card and that it stays defined for longer than a minute in a real Home Assistant.

## [2.1.7] - 2026-10-24

### Fix - Map card missing from the card picker and "Custom element doesn't exist" (diagnostic release)

- What happened: after 2.1.6 the map card file loaded (status 200) with no errors, and the card appeared in Home Assistant's list of custom cards, yet the browser reported the `metlink-map-card` element as not defined. Other custom cards (button-card, Mushroom) were defined normally. The card picker and editor then failed with "Custom element not found".
- The card now checks that its element is really defined after registering it, and writes `Metlink map card: loaded, registered = true/false` to the browser console. If the element is missing after 1, 5 or 15 seconds, it logs a warning and registers it again.
- Not yet confirmed: I do not know the root cause. This release may fix it or may only show what is happening. If the card is still missing, the console lines starting with `Metlink map card:` will tell us whether the script runs at all.
- The departure board card is unchanged.

## [2.1.6] - 2026-10-24

### Fix - Cards showed "Custom element doesn't exist" until a hard refresh

- What happened: the cards loaded, then failed after a while or when the screen changed, and only a hard refresh recovered them. Your browser console showed the card-mod add-on throwing `themesReady: Timeout waiting for themes to become ready`, with the trace running through our cards' `<ha-card>` element.
- Both cards no longer create an `<ha-card>` element. They draw their own container styled from your theme's card colour, radius, shadow and border, so card-mod has nothing to hook and can stay enabled for your other cards.
- The map card now also clears its saved map and marker state when removed from the page, so a card that is re-attached after a layout change rebuilds its map and tiles.
- Side effect: card-mod styling applied to these two cards no longer takes effect.
- Not yet confirmed: this is my best explanation, not a proven cause. It has not been tried in a real Home Assistant. The card scripts themselves loaded fine (status 200) and threw no errors.

## [2.1.5] - 2026-10-24

### Fix - Map showed "API KEY REQUIRED" and spilled out of its card

- What happened: CARTO, the map tile provider I switched to in 2.1.3, now requires an API key for its basemaps and returns a placeholder tile reading "API KEY REQUIRED". My 2.1.3 check only confirmed the tile address responded, not that it was a real map.
- The street map now uses Esri World Street Map and the light map uses Esri Light Gray Canvas. Neither needs an API key or a referrer, so they work inside Home Assistant. I checked that both return real map images over Wellington, not placeholders. Attribution to Esri is shown on the map.
- The map spilled out of its card and drew over the departure board. Home Assistant draws cards in an isolated style scope, so Leaflet's stylesheet (loaded into the main page) never reached the map. The stylesheet is now loaded inside the card, and the map is clipped to its own box.
- The removed `referrerPolicy` option from 2.1.3 is no longer needed.
- Not yet confirmed: the layout fix in a real Home Assistant. It was checked in a simulated browser only.

## [2.1.4] - 2026-10-24

### Fix - Only one of the two cards could load

- What happened: both card files declared the same top-level names (`WS`, `esc`, `clock`). Home Assistant loads them into the same page scope, so the second file failed with `Identifier 'WS' has already been declared` and its card never registered. The card picker then showed endless spinners and a dashboard reported "Custom element not found".
- Each card file is now wrapped in its own scope, so the two cards can no longer clash with each other or with other custom cards.
- Not caused by 2.1.3: that release only changed the map tile source. The clash was already present in 2.1.0.
- Why this was missed: the earlier browser check loaded each file in its own scope, which hid the clash. Both files are now tested together in one page.
- Not yet confirmed: that this alone fixes the picker on a real Home Assistant. If a card is still missing, send the browser console errors.

## [2.1.3] - 2026-10-24

### Fix - Map showed "403 Access blocked" instead of the street map

- What happened: the map card loaded its tiles from OpenStreetMap's own volunteer-run servers, which replied "Access blocked". Their tile usage policy requires requests to identify the website they come from, and Home Assistant tells browsers not to send that information.
- The default street map now uses CARTO Voyager, a street-style map from a provider that does not have that restriction. It still credits OpenStreetMap and CARTO.
- Tile requests now also send the site's origin as the referrer.
- Your saved choices (modes, routes, light map) are unaffected.
- Why this was missed: the card had never been shown in a real browser before 2.1.0 was installed.

## [2.1.2] - 2026-10-24

### Fix - Cards did not load when an old version 1 entry was present

- What happened: after updating from version 1, the old entries (Ferry, Train, Bus, School Bus) were still in Home Assistant. They have no Metlink key, so setup failed with `KeyError: 'metlink_api_key'`. Because the cards were only registered after a successful setup, neither card loaded.
- The cards are now registered as soon as the integration loads, whether or not an entry sets up successfully.
- A leftover version 1 entry now fails with a clear message ("delete it, then add Metlink Explorer again") instead of a `KeyError`.
- A second entry is rejected with a clear message rather than clashing with the first.
- What you need to do: delete any old Metlink Explorer entries and add the integration again with your keys. Version 1 entries cannot be converted.
- Why this was missed: version 2 had never been run in a real Home Assistant with version 1 entries still present. A new test now covers both cases.

## [2.1.1] - 2026-10-24

### Change - Version 2 is now on the main branch

- Why: HACS installs from the repository's default branch (`main`), and version 2 was released from a separate `v2` branch while it was being built. Nobody could install it through HACS. Version 2 has now been merged into `main` so it can be downloaded and tested in Home Assistant.
- No code changed in this release. It only moves version 2 (including the map card and ferry tracking from 2.1.0) onto `main`, and bumps the version number so HACS offers it as an update.
- The old version 1 code is kept in the `legacy` folder for reference only and is not installed.

## [2.1.0] - 2026-10-24

### Feature - Live map card

- Why: 2.0.0 shipped only the departure board. The map was the other half of the integration and the reason for the rebuild: version 1's map relied on entity attributes, which is where the connection leaks and rate limits came from.
- New `metlink-map-card` on a Leaflet street map. Home Assistant's built-in map cannot draw route lines or stop markers, which is why Leaflet is used. It is loaded from unpkg with integrity hashes, so a tampered file would be refused.
- It starts as a plain street map. You pick the modes (bus, train, ferry, cable car) and routes (up to 12); your choices are remembered per browser.
- Route lines use the route colours, live vehicles show the route number and a heading arrow, and stops with a pair on opposite sides of the road appear as one marker. Clicking a stop shows its next departures.
- Stops are only fetched for the visible area and only once you zoom in, so the card never asks for thousands of markers at once.
- Toggles for school buses, stops and a lighter basemap.
- Trains were already tracked: Metlink's vehicle feed covers buses, trains and the cable car, so the map shows them with no extra work.

### Feature - Live ferry positions

- Why: Metlink's vehicle feed does not include ferries, so they come from AISStream instead (the optional key entered during setup).
- Only one AISStream connection exists per Home Assistant instance, however many browsers and cards are open. This is the direct fix for version 1 opening over 100 connections.
- It connects only while a map card is subscribed and disconnects when the last one closes.
- Failure handling is separate from the Metlink feeds: a rate limit waits two minutes, other errors retry with a growing delay (30 seconds up to 10 minutes), and a rejected key stops retrying until the key is changed. None of this affects bus or train data.
- Updates are limited to one every 5 seconds, and a ferry not heard from for 15 minutes is removed from the map.
- The status command now reports whether ferry tracking is connected and how many ships are tracked.

### Development

- 6 new tests cover the ferry parser, the single shared connection, backoff, key rejection and merging ferries into the vehicle list (70 tests in total).
- Not yet verified: the map card in a real browser and the live AISStream feed. Both are tested for the first time by installing this version.

## [2.0.0] - 2026-10-24

### Breaking - Version 2 is a rebuild and is not compatible with version 1

- Why the major version: the whole integration was rebuilt from scratch. Almost nothing from version 1 carries over, so continuing the 1.x numbers would have misled anyone updating.
- There are no longer any sensors. Version 1 created two entities for every route you chose. Version 2 creates none, so any dashboard, card or automation that used those entities will stop working.
- The setup steps for choosing a transport type and a route are gone. Setup now only asks for the Metlink API key (and, optionally, an AISStream key). Your choice of stops and routes is now made inside the card.
- The old cards (the map, the departure board and the editor) have been removed. They depended on the entities above. A new departure board card replaces the old one. A new map card is not ready yet.
- Automations are no longer possible. The live data only updates about once a minute, which is too slow for triggers such as "the bus is 500 m away", so the integration does not offer them.
- What you need to do: remove the old Metlink Explorer integration and its cards from your dashboards, restart Home Assistant, add the integration again with your API key, and add the new **Metlink Departure Board** card. The old v1 code is kept in the `legacy` folder in the repository for reference only.

### Change - Why version 2 was needed

- Version 1 could break itself. An error log showed the ship-tracking websocket (AISStream) being refused more than 150 times in a short period, and the Metlink API itself refusing requests as well. Home Assistant then reported "Error fetching metlink_explorer data" and no departures were shown.
- Root cause: every time Home Assistant set up the integration, it started its own private ship-tracking connection, and those connections were never shut down when a setup failed or was merged into another. After a few failed setups there were more than 100 connections running at once, each retrying and each counting against the single AISStream key. Metlink data was requested in the same loop, so one failing source took the other down with it.
- The fix could not be a small patch. The data collection, the entities, the cards and the schedule building were all tangled together, and each route created its own copy of the work. Rebuilding with separate, independent parts was safer than patching.
- The design goals for the rebuild were: only one ship-tracking connection no matter what; ship and bus failures must never stop each other; nothing is requested from Metlink while no one is looking at a card; and the card, not the integration, should hold your choices.

### Feature - A data service instead of entities

- The integration is now a background data service. It downloads and stores the timetable, collects live data, and serves both to the cards over Home Assistant's own authenticated websocket connection. Only people logged in to Home Assistant can read it.
- Home Assistant only. There is no separate web interface for other software.
- Phones, laptops and tablets that open your dashboard share the same single service. Opening a new browser does not start a new copy of anything.
- Live data is only requested while at least one card is open. With no cards open, the integration makes no live requests to Metlink.

### Feature - The whole timetable is stored on disk and refreshed daily

- The full Metlink timetable (every route, stop, trip, stop time, shape and calendar) is downloaded as Metlink's single GTFS file and stored in a local database on disk, not in memory. The database was about 54 MB when tested.
- Once a day the integration asks Metlink whether the timetable changed. If it has not, nothing is downloaded or rebuilt. If it has, a new database is built beside the old one and swapped in only when complete, so a failed or interrupted download never leaves you without a timetable.
- The first download runs in the background so Home Assistant starts normally. On a slow machine it can take several minutes.
- Buses, trains, the ferry and the cable car are all included. School buses are marked with a school flag so cards can show or hide them. The cable car is kept as its own type.

### Feature - Choose where you are going, and always see the right schedule

- The question was how to show the correct schedule for the direction you want to travel, for example catching the 83 at Muritai Road and heading to Wellington.
- Version 1 labelled trips "inbound" or "outbound" and worked out which was which with its own guesswork. We tested this against Metlink's live departures and found it is not reliable: on cross-town routes, loops and regional routes there is no single "towards the city", and even Metlink's own inbound/outbound label is only a route code, not a geographic direction. Our guesses agreed with Metlink only about 65% of the time.
- In version 2 you pick the stop and then pick where you are heading ("Towards Courtenay Place"). The list of choices is built from the real trips that call at your stop, and you only see trips that stop at your chosen place afterwards. This uses the actual timetable, so it is correct for every kind of route.
- The two stops on opposite sides of a road are shown as one marker with one set of departures, and the opposite-side stops are matched using names, streets, distance and Metlink's stop numbering (stops on opposite sides often differ by exactly 1000). The match is scored and the reason is stored.
- Departures show the next 20 trips within the next 72 hours by default (up to 168 hours if a card asks). Times after midnight and public holiday changes are handled.
- A towards/away-from-the-centre label is still worked out for each stop and kept for the map, but it is never used to decide which schedule you see.

### Feature - Live delays, cancellations and alerts

- Live vehicle positions, trip updates and service alerts are collected from the three Metlink live feeds, each on its own. If one feed fails, the others and the last good data keep working.
- Delays, early running, cancelled trips and skipped stops are added to each departure. A delay reported at one stop carries on to the following stops until the next update, as the GTFS standard describes.
- Live vehicles are matched to routes through their trip, not their route number, because Metlink's live route numbers do not match its timetable (for example the Johnsonville line is 63 live but 6 in the timetable).
- The feeds are checked every 30 seconds (alerts every 3 minutes) while a card is open. Metlink's trip update feed sometimes refuses requests even at gentle rates, so each feed backs off by itself, honours any "retry after" request from Metlink, and keeps showing the previous data until the next good answer. If Metlink rejects the API key, only the feed that was refused stops.

### Feature - New departure board card

- Search for a stop by name or stop number, choose where you are heading, and see departures counting down live, with route colours, delays, cancellations and a school-bus tag.
- Your choice is remembered in that browser, and each card cleans up its live connection when it is removed from the dashboard.

### Change - Simpler setup

- Setup asks for the Metlink API key and checks it with Metlink. A busy answer from Metlink is accepted, because the key itself was accepted. An optional AISStream key can be entered, and keys can be changed later through Reconfigure.
- Only one Metlink Explorer can be set up at a time.

### Change - Development process and tests

- The code is split into separate parts for the Metlink connection and backoff, the database, the timetable download, the direction and stop-pairing logic, the departures, the live feeds and the card-facing commands, each with its own tests (64 tests).
- `AGENT_INSTRUCTIONS.md` was added. It sets out how automated assistants must work in this repository, including the release procedure used for this release.
- Old test and debug scripts were removed. One of them contained a Metlink API key in the repository history, so that key should be treated as exposed and replaced. No keys are included in this release.

### Known gaps in this release

- The live map card is not yet rebuilt. Until it is, there is no map.
- Live ferry positions (AISStream) are not yet connected. The key can be entered, but it is not used yet. The planned design is a single shared connection for the whole of Home Assistant.
- The integration has been tested with automated tests and against the live Metlink API, but has not yet been run in a full Home Assistant installation.

## [1.0.13] - 2026-05-27

### Fix - School bus inbound/outbound departures now visible

- Fixed school bus routes (and other routes without stop_pair_index data) showing no inbound departures.
- Root cause 1: the schedule database window was only 24h (today + tomorrow). School buses do not run on weekends, so on a Friday afternoon, the 24h window contains no inbound rows for Monday.
- Root cause 2: routes with missing/empty stop_pair_index were skipped from `routeInboundMap`, so their raw numeric direction keys (`"0"`/`"1"`) were never normalized to `"inbound"`/`"outbound"`. At a mixed bus+school bus stop, this caused school bus rows to be filtered out by the inbound/outbound tabs.
- Fix 1: Schedule window extended to 72h (3 days) and the API now fetches service dates for the full window, ensuring school-day routes are included even over weekends.
- Fix 2: `_buildRouteInboundMap` now includes all routes with a fallback to GTFS default (inbound = direction_id 1) when stop_pair_index is missing. This ensures all routes enter the map and get normalized at filter/render time.

## [1.0.12] - 2026-05-27

### Fix - Bus shared-stop bubbles now include outbound departures from all nearby routes

- Fixed outbound bus routes not appearing in departure bubbles at shared bus stops and interchanges.
- Root cause: the fallback opposite-stop scan was limited to the clicked route's geometry feature set only, so opposite bays served by other bus routes were never added to the departure stop scope.
- Additionally, bus departure scope was restricted to a single paired stop ID, missing nearby bays and platforms on the opposite side of the road.
- Fix: for bus mode, fallback pairing now scans all visible bus route entities globally (same approach as `routeInboundMap` scanning introduced in v1.0.9).
- Fix: bus departure scope is expanded to include up to 8 nearby opposite-direction stop IDs within 120 m (180 m for terminus stops), using the new `_nearbyOppositeStopIds` helper.
- Train and ferry pairing logic is unchanged.

## [1.0.11] - 2026-05-27

### Fix - Bus shared-stop inbound/outbound filtering now includes all routes correctly

- Fixed mixed shared-stop direction filtering where bus departures from some routes could disappear under Inbound/Outbound tabs.
- Expanded route inbound-direction lookup to support route ID and route short name keys when normalizing row direction keys.
- Added per-row direction key normalization during filter and badge evaluation, so rows that arrive with numeric keys (`0`/`1`) still match semantic Inbound/Outbound filters.
- Kept train shared-station behavior aligned with the same robust normalization path.

## [1.0.10] - 2026-05-27

### Feature - Colour-coded inbound/outbound direction indicators

- Inbound filter button and row badge are now **amber** (`#f59e0b`) — warm colour for travel towards the city.
- Outbound filter button and row badge are now **teal** (`#0891b2`) — cool colour for travel away from the city.
- Active filter button uses the full colour as its background; inactive state shows a tinted border and text to hint the available direction.
- Per-row direction chip on each departure card uses a matching translucent pill style for inbound (amber) and outbound (teal).
- Colour coding applies consistently across all modes: train, bus, and ferry stops.
- Neutral "All" button retains the existing white active state.

## [1.0.9] - 2026-05-28

### Fix - Shared train/bus stop bubbles now show all routes (e.g. WELL shows KPL, HVL, MEL, JVL, WRL)

- Fixed departure bubbles at shared train and bus stops showing only the clicked route's departures instead of all routes serving that stop.
- Root cause: the per-route direction normalisation map (`routeInboundMap`) was built only from the clicked route entity's geometry features. Rows from other routes at the same stop kept raw numeric `directionKey` values (`"0"`/`"1"`) that didn't match the `"outbound"` tab filter, making them invisible.
- Fix: for train and bus mode, the direction normalisation map is now built from all same-mode route entities configured in the card, so every route's `inbound_direction_id` is known before direction tabs are applied.
- Wellington Station (`WELL`) and all other shared Wellington suburban train stations now correctly display departures from all lines (KPL, HVL, MEL, JVL, WRL).

## [1.0.8] - 2026-05-27

### Fix - Automatic terminus selection for train and bus routes

- Restored automatic terminus selection for all train and bus route entries in the map card, even when no manual `selected_stops` are configured.
- Terminus stop IDs are now mode-normalized before selection and fallback expansion, keeping train platform variants aligned with station IDs.
- Selected-stop influence indexing now includes auto-selected termini, improving shared-station/stop grouping behavior.
- Card editor now auto-populates train and bus `selected_stops` with route termini when an entity is chosen and no stops are manually selected.
- Editor stop normalization now treats train platform suffixes consistently so terminus selections remain stable.

## [1.0.7] - 2026-05-27

### Fix - Bus shared-stop bubbles now show mixed routes

- Removed route-level scoping for bus stop bubbles so shared bus stops show departures from all bus routes serving that stop, not just the clicked route.
- Keeps route scoping for other non-train/non-bus modes to avoid cross-route leakage where stop sharing is not desired.

## [1.0.6] - 2026-05-27

### Fix - Train station bubbles now show mixed routes

- Removed route-level scoping for train stop bubbles so shared stations (for example `WELL`) show departures across all train routes serving that station.
- Keeps route scoping for non-train modes to avoid cross-route leakage in bus/ferry/cable bubbles.

## [1.0.5] - 2026-05-26

### Fix - Backend train stop normalization across all DB schedule entries

- Added canonical train stop ID normalization in backend schedule generation so platform variants (e.g. `WELL1`, `WELL2`, `PETO0`, `PETO1`) are collapsed to station IDs (e.g. `WELL`, `PETO`).
- Applied normalization to both schedule row `stop_id` values and DB `by_stop` keys before writing `/local/metlink_explorer/db/train_schedules.json`.
- Added dedupe for merged train rows and stable per-stop sorting after normalization.
- Normalized train timeline stop IDs in route geometry metadata so train stop identifiers stay consistent across DB payloads.

## [1.0.4] - 2026-05-26

### Fix - Train stop departures missing on some stations

- Fixed train departure lookup against DB `by_stop` payloads by expanding bubble stop matching to include all platform keys that normalize to the same station ID.
- This resolves cases where some stops on a train line showed no departures while other stops on the same line worked.
- Fixed fallback board parsing bug where `direction_id` could be referenced before initialization when resolving direction labels.

## [1.0.3] - 2026-05-26

### Fix - Bubble pairing subtitle, route direction labels, and terminus zero-results fallback

- Restored nearby-stop bubble subheading behavior by re-enabling a route-scoped pairing fallback scan when backend pair index has no usable pair entry.
- Direction display text for rows now uses route sensor attributes `direction_0_label` / `direction_1_label` (matched by `route_id`) when available, with destination text only as fallback.
- Added a terminus fallback in bubble loading: when a terminus click returns zero rows, the card retries with terminal sibling stop IDs from the same route feature set, recovering expected early-morning departures at endpoints.

## [1.0.2] - 2026-05-26

### Fix - Correct route labels and direction chips in stop bubbles

- Scoped bubble departure queries to the clicked route's `route_id` set, preventing unrelated route rows from appearing at shared stop IDs.
- Applied the same route scoping to both DB schedule-path and legacy board fallback-path row builders.
- Updated departure direction chip rendering to show `Inbound`/`Outbound` whenever a row maps to a known direction key, even when only one direction is currently present in the bubble window.

## [1.0.1] - 2026-05-26

### Fix - Recorder attribute size and DB write race resilience

- Prevented DB write race failures in `db_manager.async_write_db_file` by switching to unique temp files per write and atomic `os.replace`.
- Added best-effort error handling around coordinator vehicle DB persistence so transient file-write issues no longer break route coordinator refresh cycles.
- Reduced Recorder payload pressure by truncating large service alert text attributes on mode departure-board sensors, preventing attribute blobs from exceeding Home Assistant's 16KB recorder storage threshold.

## [1.0.0] - 2026-05-26

### Major - Local JSON database architecture and performance refactor

- Introduced a local DB pipeline under `/local/metlink_explorer/db/` with mode-scoped files and `meta.json` timestamp tracking.
- Added DB manager helpers and DB coordinators for static route/stops/geometry snapshots, hourly schedules, and 5-minute alerts.
- Merged Bus and School Bus into a single Bus database mode so route/schedule payloads are unified.
- Added backend schedule-window builder in the API client to generate next-24h departures grouped by stop.
- Added vehicle snapshot writes to DB from the 30-second live coordinator path.
- Updated map card to poll DB metadata, cache DB files in-memory, and prefer DB geometry/schedules with legacy fallbacks retained.
- Updated departure board card to read DB schedules first with compatibility fallback to legacy sensor-derived payloads.
- Updated editor to read DB route geometry for stop pickers when available, with fallback retained.
- Simplified sensor layer into thin DB URL wrappers to reduce duplicate payload file writes.

## [0.14.5] - 2026-05-26

### Fix - Correct inbound/outbound direction detection for all routes

- Replaced the Wellington Central stop-proximity heuristic with a **net-displacement method**: the direction whose last stop is closer to Wellington Central than its first stop is classified as inbound. This correctly identifies the travel direction even for routes whose entire path lies near the CBD (e.g. Courtenay Place termini where both direction stops are within 500 m of the city).
- Backend `_build_stop_pair_index` (api.py) and frontend fallback `_inboundDirectionIdForRoute` both updated to use net-displacement.
- Added `_buildRouteInboundMap` and `_normalizeRowDirectionKeys` to the map card: departure rows now have their raw GTFS `direction_id` ("0"/"1") rewritten to stable semantic labels ("inbound"/"outbound") per route before being stored in the bubble state. This means each route's departures are classified independently, so mixed-route stop bubbles (e.g. a shared terminus serving multiple routes) label directions correctly even when Metlink uses `direction_id` inconsistently across routes.
- `_deriveDirectionMeta` detects pre-normalised "inbound"/"outbound" keys and uses them directly, bypassing the numeric-key path entirely for normalised rows.
- Filter tabs ("Inbound", "Outbound") and per-row direction badges now reflect actual travel direction rather than arbitrary `direction_id` values.

## [0.14.4] - 2026-05-27

### Improvement - Backend stop pairing table for faster map bubble lookups

- Stop pairing (inbound/outbound match-up) is now computed once in the backend when route geometry is fetched and cached with the weekly geometry refresh, instead of being re-scanned in the browser on every stop click.
- Each route's GeoJSON feature now includes a `stop_pair_index` dict keyed by stop ID, with pre-computed fields: `direction_id`, `is_terminus`, `has_pair`, `paired_stop_id`, `paired_stop_name`, `pair_distance_m`, and `inbound_direction_id`.
- The `inbound_direction_id` per route is determined by Wellington Central proximity (500 m threshold) in the backend; the frontend no longer needs to scan stop coordinates at click time.
- Map card `_openDepartureBubble` now performs an O(1) index lookup rather than an O(n) timeline scan to resolve paired stop and inbound direction.
- Frontend scanning methods (`_findPairedOppositeStopInFeatures`, `_findPairedOppositeStop`, `_inboundDirectionIdForRoute`) are retained as fallbacks for cached features that pre-date this release.

## [0.14.3] - 2026-05-26

### Fix - Bubble loading resilience and terminus stop handling

- Prevented departure bubbles from getting stuck on "Loading departures..." by adding board payload fetch timeout handling and a fail-safe empty-state fallback.
- Terminus-only stops no longer pair with nearby opposite-direction stops, avoiding incorrect extra departures at route endpoints.
- Route start/end terminus stops are now automatically displayed on the map even when not selected in the editor.
- Preserved departure-only behavior for termini by keeping endpoint arrival rows excluded from board rows.

## [0.14.2] - 2026-05-26

### Feature - Inbound/outbound stop pairing and geographical stop picker

- Map bubble now auto-detects the nearest opposite-direction stop on the same route within 50m and includes its departures alongside the clicked stop's departures.
- Bubble subheading shows the paired stop name (e.g. "+ Muritai Road at Makaro St Gardens") when a pair is found.
- Inbound/Outbound direction labels are now determined by proximity to Wellington Central Station rather than first-seen departure order, giving stable filter tabs regardless of time of day.
- Editor bus stop picker now lists stops in geographical order along the route (spine-projected sort) so inbound/outbound stops near each other appear adjacent rather than grouped by direction block.

## [0.14.1] - 2026-05-24

### Fix - Stop-only departure bubbles and full service alert attributes

- Tightened departure row construction to use only true `departure_time` events (no arrival-time fallback), improving board accuracy.
- Changed map bubble stop scoping to strict clicked-stop-only filtering so each bubble shows departures for that stop only.
- Kept past departures excluded via existing ETA/upcoming filtering behavior.
- Added GTFS-RT service alert download and mode grouping in the API client.
- Added mode alert attributes for conditional cards: `train_alert`, `bus_alert`, `ferry_alert`.
- Added explicit alert status booleans: `train_alert_status`, `bus_alert_status`, `ferry_alert_status`.
- Expanded alert parsing to capture full message content (all translation entries plus description/cause/effect/url text).

## [0.13.5] - 2026-05-23

### Fix - Tune bubble route wash starting opacity

- Adjusted departure row route-colour gradient to start at 75% opacity (`bf` alpha) instead of fully opaque.
- Retained fade to black at 40% width and existing white text with black outline/glow readability treatment.

## [0.13.4] - 2026-05-23

### Fix - Make bubble route wash fully opaque

- Removed transparency from departure row route-colour gradient wash.
- Updated gradient to fade from fully opaque route colour at the left edge to fully opaque black at 40% width.
- Preserves improved white route text readability with black outline/glow on top of the stronger wash.

## [0.13.3] - 2026-05-23

### Fix - Bubble route text readability on bright colour washes

- Increased departure row colour wash gradient fade distance to 40% of bubble card width.
- Replaced light-colour text switching with a consistent white route label style plus a strong black outline/glow via text-shadow.
- Ensures route IDs remain legible across bright and saturated route colours without switching to dark text.

## [0.13.2] - 2026-05-23

### Fix - Departure bubble gradient width and fallback coverage

- Updated departure row gradient fade distance from 15% to 35% of bubble card width.
- Fixed route colour wash application for non-train rows by carrying route identifiers (`route_id`, `service_label`) in bubble departure rows and resolving colours from those keys.
- Set default fallback route wash colour to black (`#000000`) when no configured route colour can be resolved.
- Kept light-colour route number contrast fallback logic so route labels switch to dark text on bright washes.

## [0.13.1] - 2026-05-23

### Fix - Route colour gradient rendering and contrast fallback

- Fixed colour gradient not rendering: colour is now computed at render time using `bubble.stop.mode` as a guaranteed fallback, so a mode-default colour (bus green, train blue, ferry teal) is always applied even when no per-route config entry is matched.
- Made the colour lookup more robust: now checks entity state attributes (`route_id`, `route_short_name`), geojson feature properties, and entity ID parsing in a combined set before matching, rather than stopping at the first path that returns nothing.
- Raised gradient start opacity from 25% (`4d` hex) to 30% (`4d` → kept) for better visibility on dark backgrounds.
- Added `_isLightColor()` helper using WCAG 2.1 relative luminance: when the resolved route colour has luminance > 0.35 (e.g. yellow, light green), the route number text switches to `#111` dark with no text-shadow to maintain readability.

## [0.13.0] - 2026-05-23

### Added - Route colour gradient wash on departure bubble route IDs

- Stop bubble departure items now display a subtle colour gradient wash behind the route number (e.g. "1", "83").
- The gradient starts with the configured route colour at the left edge and fades to transparent over approximately 15% of the card width.
- Colour is resolved from the matching configured route entry for the departure's route short name across all transport modes (bus, train, ferry, cable car).
- Falls back to the mode default colour (bus green, train blue, ferry teal) when no per-route colour is configured.
- Applied to all bubble pop-out cards including bus, train, ferry, and cable car stops.

## [0.12.38] - 2026-05-13

### Fix - Enforce strict inline mixed ferry badge alignment

- Reworked mixed ferry/non-ferry hub offset placement to use a single harbor-axis inline sequence.
- Kept ferry badges closest to harbor anchor and placed non-ferry badges progressively farther away on the same line.
- Removed split-around-center behavior that could produce non-inline two-badge layouts.

## [0.12.37] - 2026-05-13

### Fix - Ferry bubble departure line shows stop-specific origin

- Updated ferry departure row display text to render as `stop_name - destination`.
- Corrected stop 9999 bubble lines to show departures originating from Days Bay Wharf instead of route-level Queens Wharf phrasing.
- Applied this display change only to ferry rows; other modes remain unchanged.

## [0.12.36] - 2026-05-13

### Fix - Align ferry QDF/MIF service label mapping

- Updated ferry trip service-label classification so Mātiu/Somes-linked patterns map to `QDF` and non-Mātiu counterparts map to `MIF`.
- Corrected stop 9999 bubble departures to show `QDF` labels according to configured route semantics.
- Kept strict ferry stop-only bubble filtering behavior introduced in `0.12.35`.

## [0.12.35] - 2026-05-13

### Fix - Ferry bubbles show departures for clicked stop only

- Applied ferry-only strict stop filtering in departure bubbles so ferry stops no longer aggregate nearby/influence stop departures.
- Limited ferry bubble departure queries to the exact clicked stop ID.
- Removed direction filter chips from ferry bubbles and disabled ferry-specific outbound-only forcing.
- Kept train, bus, and cable bubble behavior unchanged.

## [0.12.34] - 2026-05-13

### Fix - Ferry service classification and stop dropdown completeness

- Refined ferry MIF/QDF classification to prioritize destination/headsign place names (Days Bay/Queens Wharf vs Matiu/Somes) before stop-pattern fallback checks.
- Fixed Days Bay departures being mislabeled as MIF in stop bubbles.
- Changed route stop-pattern selection to choose the most complete trip pattern per direction instead of the first trip.
- Restored intermittent ferry stop `9998` (Matiu/Somes Island Wharf) in timeline-derived editor stop dropdowns.

## [0.12.33] - 2026-05-13

### Fix - Ferry destination arrivals excluded from departures board

- Excluded terminal-stop rows for all modes when building timetable departure rows.
- Prevented destination arrivals from being surfaced as departures in stop bubbles and mode boards.
- Fixed Queens Wharf (stop 9997) showing Days Bay arrivals as departures.

## [0.12.32] - 2026-05-13

### Fix - Citations and zoom-aware distance scale

- Added map citation text along the bottom of the map.
- Added Metlink API citation link.
- Added AISStream API citation link.
- Added a live metric distance scale control that updates with map zoom.
- Updated frontend build marker to `0.12.32`.

## [0.12.31] - 2026-05-13

### Fix - Layer menu close behavior consistency

- Added 30-second inactivity auto-close for the layer hamburger menu.
- Ensured the menu closes when the user clicks elsewhere on the card.
- Merged duplicate lifecycle setup so outside-click listeners are always registered.
- Added proper panel auto-close timer cleanup on component disconnect.
- Updated frontend build marker to `0.12.31`.

## [0.12.30] - 2026-05-13

### Fix - Outbound-only terminal train and bus stop bubbles

- Forced train stop bubbles to outbound-only when the stop is a route start/end terminal on visible train routes.
- Forced bus stop bubbles to outbound-only only when the stop is terminal and no visible bus routes pass through it.
- Kept pass-through bus hubs (for example Courtney Place with through-services) on normal direction filtering.
- Applied terminal detection against visible route timeline stop sequences for consistency with map layer visibility.
- Updated frontend build marker to `0.12.30`.

## [0.12.29] - 2026-05-13

### Fix - Ferry stop bubbles outbound-only departures

- Limited ferry stop bubble cards to outbound departures only.
- Locked ferry bubble direction filtering to outbound to prevent inbound/all selection for ferry stops.
- Applied ferry-specific direction metadata handling so outbound remains the active scope.
- Updated frontend build marker to `0.12.29`.

## [0.12.28] - 2026-05-13

### Fix - Inline ordering for mixed ferry/train/bus stop badges

- Replaced radial/fan placement in ferry-mixed groups with strict inline ordering.
- Kept ferry as the primary anchor closest to the harbor center direction.
- Forced non-ferry badges to line up in one sequence at increasing distance from the ferry anchor (no side spread).
- Applied the same inline rule in both the source-offset pass and the overlap-layout pass for redraw consistency.
- Updated frontend build marker to `0.12.28`.

## [0.12.27] - 2026-05-13

### Fix - Harbor-anchored ferry badge priority

- Anchored ferry-containing badge groups to the Matiu Somes Island harbor center so ferry badges remain the primary visual anchor.
- Placed non-ferry badges progressively farther from the harbor center instead of allowing generic overlap packing to reshuffle ferry priority.
- Preserved ferry-first ordering inside the overlap solver so map redraws and resizes no longer move ferry badges behind train or bus badges.
- Updated frontend build marker to `0.12.27`.

## [0.12.26] - 2026-05-13

### Enhancement - Smart ferry stop positioning toward harbor centers

- Implemented mode-aware hub positioning logic that places ferry stops closest to harbor centers (e.g., Matiu Somes Island in Wellington Harbour).
- Ferry stops now position at 60% radius toward the nearest harbor center when mixed with other mode stops (train/bus).
- Other mode stops (train, bus, cable) arrange in a circular pattern further from the harbor center.
- Harbor center coordinates configurable for different regions (currently hardcoded for Wellington).
- Improves visual clarity by separating ferry badges from train/bus badges in multi-mode hubs.
- Updated frontend build marker to `0.12.26`.

## [0.12.25] - 2026-05-13

### Fix - Badge collision logic continuous operation and resilience

- Fixed badge collision logic stopping after ~120 seconds by adding persistent live update timer that runs every 5 seconds after startup settles.
- Ensured badge overlap recalculation fires on all live vehicle data updates (e.g., ferry position changes).
- Badge collision logic now stays active indefinitely with continuous periodic re-evaluation.
- Timer automatically restarts if the integration restarts while kiosk is open.
- Improved consistency of badge layout when map moves, zooms, or rotates.
- Updated frontend build marker to `0.12.25`.

## [0.12.24] - 2026-05-13

### Fix - Train station suffix collapse and badge layout resilience

- Collapsed multiple train station badges for co-located station suffix variants (for example `WELL1`, `WELL2`, `WELL3`) into a single badge with merged departure information.
- Applied global canonical-key deduplication across all route data sources to prevent duplicate badges.
- Enhanced stop badge overlap layout engine to re-trigger on window/container resize events for improved reliability.
- Updated frontend build marker to `0.12.24`.

## [0.12.23] - 2026-05-13

### Fix - Collapse co-located station suffix stop badges

- Normalized train station stop IDs to collapse numeric suffix variants (for example `WELL1`, `WELL2`, `WELL-3`, `WELL_4`) to a shared station key.
- Updated train stop badge dedupe to collapse only when those normalized station variants are co-located.
- Preserved aggregated departure behavior for the merged station badge.
- Updated frontend build marker to `0.12.23`.

## [0.12.22] - 2026-05-13

### Fix - Stop badge overlap realignment and kiosk startup redraw resilience

- Added pixel-accurate stop badge overlap grouping and inline re-layout with a 3px gap centered on the overlap midpoint.
- Applied overlap logic to stop badges only, with live vehicle markers excluded.
- Added automatic stop badge re-alignment on zoom/rotate/move-end map changes.
- Ensured stop visibility toggles immediately trigger redraw/re-alignment and hidden stop modes are excluded from overlap grouping.
- Reduced nearby stop influence grouping radius from 200m to 75m to better match true hub/adjacent-stop behavior.
- Added forced overlay redraw loop every 10 seconds during integration startup and auto-stop once stable, including automatic re-arm after restart.
- Updated frontend build marker to `0.12.22`.

## [0.12.21] - 2026-05-13

### Improvement - Stop influence aggregation clarity in departure bubble

- Added a bubble subtitle that appears when nearby-stop aggregation is active: `Aggregated from N nearby stops`.
- Kept this as a map visualization-only change with no entity model changes.
- Updated frontend build marker to `0.12.21`.

## [0.12.20] - 2026-05-13

### Fix - Ferry live tracking continuity and websocket resilience

- Changed AIS websocket reconnect backoff to 60 seconds when disconnected.
- Disabled server-side MMSI websocket filtering and kept MMSI filtering local to avoid upstream over-filter suppression.
- Extended in-memory ferry report retention horizon so sparse AIS transmissions continue to plot instead of dropping after 20 seconds.
- Removed ferry position cache reuse in the API call path so latest buffered coordinates are normalized each update cycle.
- Updated frontend build marker to `0.12.20`.

## [0.12.19] - 2026-05-12

### Fix - Critical: AIS websocket position buffer not being populated

- Fixed missing MMSI extraction from AIS report dict before use in logging (caused undefined variable error).
- **Fixed critical bug**: Position reports were never being stored in `_ais_live_reports` buffer; loop processed and logged messages but never persisted them.
- Added startup diagnostic logging to `_ensure_ais_stream_task()` to show whether AIS background task is created and running.
- Updated frontend build marker to `0.12.19`.

## [0.12.18] - 2026-05-12

### Improvement - Debug logging for AIS websocket stream lifecycle

- Added iteration-level debug logging to track AIS stream loop start, connect, subscribe, and reconnect events.
- Added per-message debug logging showing MMSI position updates with lat/lon coordinates as they arrive.
- Added periodic health check logging (every 60 seconds) reporting total messages and buffered position count.
- Added iteration summary logging when websocket closes showing total messages and position updates for that connection.
- Updated frontend build marker to `0.12.18`.

## [0.12.17] - 2026-05-12

### Fix - Maintain persistent AISStream websocket connection

- Replaced short-lived AIS websocket sampling with a persistent background websocket connection while the integration is running.
- Send AIS subscription immediately on connect/reconnect and keep a live in-memory report buffer for ferry updates.
- Added clean integration unload shutdown to cancel the AIS background task and close the stream lifecycle safely.
- Updated frontend build marker to `0.12.17`.

## [0.12.16] - 2026-05-12

### Fix - Enforce strict configured ferry MMSI filtering

- Enforced strict MMSI filtering when a configured ferry vessel map is present.
- Disabled adaptive MMSI fallback in strict mode so unrelated harbour vessels are not learned into ferry tracking.
- Preserved adaptive fallback behavior only when no explicit vessel map is configured.
- Updated frontend build marker to `0.12.16`.

## [0.12.15] - 2026-05-12

### Fix - Keep ferry trackers visible while stationary

- Disabled 120-second stale-data expiry for ferries in backend tracker retention (indefinite keep-alive).
- Disabled live_max_age_seconds freshness filtering for ferries on frontend map (ferry markers persist until removed from coordinator).
- Other transport modes (Train, Bus, Cable Car, School Bus) retain existing 120-second timeout behavior.
- Updated frontend build marker to `0.12.15`.

## [0.12.14] - 2026-05-12

### Fix - AISStream ferry subscription resilience and fallback handling

- Removed server-side `FiltersShipMMSI` from AIS websocket subscription to avoid upstream over-filtering when live MMSIs drift.
- Increased AIS sampling window from 8 seconds to 20 seconds to reduce empty websocket sample windows.
- Added AIS server error-payload logging and fixed receive-count diagnostics in websocket polling logs.
- Kept local ferry normalization safeguards, including single-MMSI fallback when strict filtering yields no matches.
- Updated frontend build marker to `0.12.14`.

## [0.12.13] - 2026-05-12

### Fix - Update ferry MMSI mapping to MarineTraffic values

- Updated the default ferry MMSI map to the current MarineTraffic values for IKA RERE, COBAR CAT, and CITY CAT.
- Added startup normalization so older saved legacy ferry MMSI maps are migrated automatically.
- Updated the frontend build marker to `0.12.13`.

## [0.12.12] - 2026-05-12

### Improvement - Slow raster tile reveal timing

- Set raster tile fade duration to 250000 ms (250 seconds) for map tile loading transitions.
- Applied the fade duration consistently on initial map setup and style refresh updates.
- Updated frontend build marker to `0.12.12`.

## [0.12.11] - 2026-05-12

### Fix - Layer menu outside-click close and live marker refresh freeze

- Added global pointer-down handling so clicking outside the layer (hamburger) panel closes it immediately.
- Fixed live vehicle render loop control flow so stationary vehicles no longer abort the entire update pass.
- Corrected live marker update behavior where position updates could appear frozen after a short period.
- Updated frontend build marker to `0.12.11`.

## [0.12.10] - 2026-05-12

### Fix - Ferry live badge icon-only rendering and MIF/QDF live aliasing

- Removed ferry live badge text overlay so live ferry markers render as icon-only badges.
- Stopped ferry live badge rotation by bearing and kept east/west behavior driven only by flipped ferry icon variants.
- Added shared ferry route alias matching so `MIF`, `QDF`, and shared ferry route ids can resolve to the same live ferry trackers in the frontend.
- Updated frontend build marker to `0.12.10`.

## [0.12.9] - 2026-05-12

### Fix - Preserve saved API keys in integration options

- Fixed options flow behavior so leaving Metlink or AIS API key fields blank no longer clears previously saved keys.
- Added masked Metlink API key field to options alongside the AIS key field for explicit key overwrite behavior.
- Updated options flow validation so Metlink API key is only revalidated when a new key is entered.
- Clarified options UI copy to state that blank key fields keep existing stored values.
- Updated frontend build marker to `0.12.9`.

## [0.12.8] - 2026-05-12

### Fix - Guard map card async flows against unhandled promise noise

- Added defensive wrapper handling for fire-and-forget async map card tasks to prevent unhandled promise rejections.
- Updated map click, route render, and live render trigger paths to run through guarded async execution.
- Suppressed benign transition abort-style errors (`AbortError` / `Transition was skipped`) while still logging real failures.
- Updated frontend build marker to `0.12.8`.

## [0.12.7] - 2026-05-12

### Improvement - Configurable canonical ferry MMSI map and AIS binary frame parsing

- Added persistent canonical ferry vessel mapping storage (`MMSI -> name`) with default entries for Cobar Cat, City Cat, and Ika Rere.
- Added integration options field to edit ferry vessel mappings (one per line: `MMSI,NAME`) and propagate updates across entries sharing the same Metlink API key.
- Updated runtime setup to pass configured vessel mapping into AIS parsing so live tracker filtering uses user-managed canonical MMSI values.
- Updated AIS websocket parsing to accept binary frames in addition to text frames, improving compatibility with current AISStream payload delivery.
- Corrected seed vessel name fallback from `COBALT` to `COBAR CAT`.
- Updated frontend build marker to `0.12.7`.

## [0.12.6] - 2026-05-12

### Fix - Robust MMSI discovery from ferry vessel names

- Expanded AIS discovery sampling to include static/name-bearing message types (`ShipStaticData`, `StaticDataReport`) in addition to position reports.
- Added vessel-name extraction from multiple AIS payload locations and metadata fields to improve name availability during registry refresh.
- Normalized vessel and fleet names before matching so punctuation/case differences do not block MMSI selection.
- Allowed name-only AIS messages (without coordinates) to contribute to MMSI registry building while keeping position normalization strict for tracker updates.
- Improved registry candidate selection to prioritize confirmed East by West fleet-name matches before activity-based fallback.

## [0.12.5] - 2026-05-12

### Fix - Improve ferry tracker discovery reliability

- Increased AISStream sampling window to improve vessel capture reliability for Wellington Harbour polling cycles.
- Added setup fallback to reuse an AIS API key from sibling Metlink Explorer entries sharing the same Metlink API key.
- Updated options flow so changing AIS API key propagates to all entries for the same Metlink API key and reloads them.
- Updated frontend build marker to `0.12.5`.

## [0.12.4] - 2026-05-12

### Fix - Save API keys without forcing route selection

- Added a `Save API keys only` toggle to the `Select Transportation Type` step so users can update stored keys without adding a route.
- Fixed flow behavior where submitting API key changes could continue into route selection due to transport option preselection.
- Updated config flow copy and abort messaging to clearly indicate successful key-only updates.
- Updated frontend build marker to `0.12.4`.

## [0.12.3] - 2026-05-12

### Improvement - Masked API key override fields on transport selection

- Added password-style Metlink API key and AISStream API key override fields to the `Select Transportation Type` step.
- Leaving the fields blank keeps the currently stored keys, while entering new values overwrites the keys used for the setup flow.
- Updated transportation-type step copy to explain the optional override behavior directly in the UI.
- Updated frontend build marker to `0.12.3`.

## [0.12.2] - 2026-05-12

### Improvement - Dynamic East by West ferry discovery and clearer AIS setup

- Replaced the manual ferry MMSI configuration path with dynamic ferry discovery based on the East by West fleet page.
- Ferry AIS registry refresh now derives vessel names from the live East by West fleet website so ferry name changes do not require code changes.
- Clarified the config flow and options flow text so users enter their own Metlink API key and can optionally add their own AISStream API key for live ferry tracking.
- Removed the manual MMSI options UI and runtime override path.
- Updated frontend build marker to `0.12.2`.

## [0.12.1] - 2026-05-12

### Hotfix - Resolve ferry live rendering script syntax error

- Fixed a frontend JavaScript syntax/runtime error (`Unexpected reserved word`) in live vehicle rendering introduced in `0.12.0`.
- Replaced an `await` call inside a non-async `forEach` callback with an async-safe `for...of` loop.
- Restored map card initialization and ferry live badge rendering without browser console exceptions.
- Updated frontend build marker to `0.12.1`.

## [0.12.0] - 2026-05-12

### Feature - AIS-powered ferry live tracking and ferry live icon behavior

- Added AIS API key support in config flow and integration setup so ferry live tracking can run from AISStream.
- Implemented ferry-specific coordinator/API flow so ferry live positions come from AIS only (no Metlink live precedence/fallback).
- Added AIS sampling/cache pipeline with daily vessel registry refresh to keep East by West fleet vessel names and MMSI mappings current.
- Updated ferry live badges to render as circular markers without the map-pin pointer.
- Ferry live icon direction now follows heading variant rules: EAST uses default ferry icon orientation and WEST uses a horizontally flipped icon.
- Kept route-level editor live tracking toggle and hamburger live-layer mode toggle behavior fully applied to ferry live layers.
- Updated frontend build marker to `0.12.0`.

## [0.11.6] - 2026-05-12

### Hotfix - Prevent browser freeze from repeated layout resize updates

- Fixed a render-loop/freeze condition caused by repeated map resize calls during component updates.
- Made layout mode application idempotent so map resize only runs when the computed host height actually changes.
- Preserved card/editor layout switching behavior while removing runaway update pressure.
- Updated frontend build marker to `0.11.6`.

## [0.11.5] - 2026-05-12

### Fix - Restore stop bubble interactions after layer overlay refactor

- Removed the full-card overlay wrapper that interfered with stop click flow.
- Kept controls card-anchored while restoring reliable stop marker click handling for departure bubble cards.
- Preserved absolute map fill layout so menu anchoring remains fixed to card boundaries.
- Updated frontend build marker to `0.11.5`.

## [0.11.4] - 2026-05-12

### Fix - Keep layer controls fixed to card boundary while panning map

- Moved map UI controls into a dedicated card overlay container anchored to the card bounds.
- Layer hamburger menu is now fixed to the card top-left margin and no longer drifts with map pan/scroll interactions.
- Updated map canvas to fill the card using absolute inset layout while controls remain in a separate overlay layer.
- Updated frontend build marker to `0.11.4`.

## [0.11.3] - 2026-05-12

### Fix - Keep layer menu confined to card during dashboard editing

- Added dashboard editor preview detection for map card layout mode.
- Applied a bounded preview height while editing so absolute-positioned controls stay within card bounds.
- Switched host height to a layout variable that updates between normal dashboard mode and editor preview mode.
- Updated frontend build marker to `0.11.3`.

## [0.11.2] - 2026-05-12

### Fix - Icon size scaling consistency and YAML-aligned layer defaults

- Layer panel toggle defaults now align with YAML route settings for live tracking, so modes with live tracking disabled start in the off state.
- Stop badge sizing now scales from the `icon_size` slider for all stop marker modes (train, bus, ferry, and cable car).
- Live tracking badge resizing now updates immediately on icon size changes, including stationary vehicles.
- Constrained `icon_size` range around the 25 baseline to +/-25 percent (`19..31`) and aligned default slider midpoint to `25`.
- Updated frontend build marker to `0.11.2`.

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
