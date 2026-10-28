# Agent Instructions - Metlink Explorer

This file is for AI agents working in this repository. It is not part of the integration and is never shipped to users. Follow it exactly.

## 0. Discuss before changing
- Do NOT create, edit, delete or rename any file until the user has finished discussing the change with you.
- When the user is asking questions, exploring options or reviewing a plan, respond with analysis and recommendations only.
- Make file changes only after the user gives an explicit go-ahead (for example "do it", "implement", "add this", "go ahead"). If it is unclear whether the discussion is finished, ask.
- Once a change is approved, make only the approved changes and nothing extra.
- This rule does not cover reading files, searching, or running read-only commands. Those are always allowed.

## 1. Commit and release rules

### 1.1 No commits without a release command
- NEVER run `git commit`, `git tag`, `git push` or `gh release` unless the user issues the command `release x.y.z` (x.y.z = version number, e.g. `release 2.0.0`).
- Editing files, running tests and building are always allowed. Leave all changes uncommitted until a release command arrives.
- If the user asks for a commit without the command, ask them to issue `release x.y.z`.

### 1.2 Procedure when `release x.y.z` is issued
Run these steps in order. Stop and report if any step fails; do not skip steps.

1. **Validate**
   - `x.y.z` must be semantic version `MAJOR.MINOR.PATCH` and greater than the current version in `VERSION`.
   - Run the tests/lint available in the repo. Do not release on failures.
   - Review `git status` and `git diff` so the changelog describes everything being released.
   - **Secrets scan:** check the staged changes and new files for API keys, tokens or credentials (Metlink key, AISStream key, `.env` files, logs, test fixtures, debug output). If any are found, stop, remove them and tell the user. Never commit secrets.
   - **Consistency check:** `VERSION`, `manifest.json`, `README.md` and the newest `CHANGELOG.md` heading must all show the same version before the commit. They must also not already equal `x.y.z` from an earlier release.
   - **Breaking changes:** if the MAJOR number increases, or any change breaks existing behaviour (entity IDs, config, websocket API, card config), the changelog entry MUST include a `### Breaking - <title>` subsection that explains what breaks and what the user must do.
2. **Update the version number** to `x.y.z` in all of:
   - `README.md` (the `Version:` line near the top)
   - `hacs.json` (add a `version` field only if the file already has one; do not invent new fields)
   - `custom_components/metlink_explorer/manifest.json` (`version`)
   - `VERSION`
3. **Update `CHANGELOG.md`**
   - Insert a new section directly under the intro text and above the previous latest version.
   - Heading format: `## [x.y.z] - YYYY-MM-DD` (today's date).
   - Then one or more `### Type - Short title` subsections (Type = Feature, Fix, Change, Refactor, Docs, etc.), each followed by `-` bullets.
   - Write in plain, human-readable language describing what changed and why, including the root cause for fixes and the visible effect for users. Do NOT paste code diffs or list filenames as the explanation. Someone with no access to the code must be able to follow the history.
   - Keep the existing format and tone of earlier entries.
   - do not write "- Not yet confirmed in a real Home Assistant."
4. **Commit**
   - Stage all changes and commit with message `vx.y.z - <short summary>`.
   - Append this trailer to the commit message: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
5. **Tag and push**
   - Create tag `vx.y.z` on the commit and push the commit and the tag.
6. **GitHub release**
   - Create or update the release for tag `vx.y.z` with `gh release`.
   - Title: `vx.y.z - <short summary>` (same style as previous releases).
   - Body: the exact changelog entry for this version (the contents of the new `## [x.y.z]` section), in the same format as earlier release summaries.
   - If a release for that tag already exists, update it instead of creating a duplicate.
7. **Failure and rollback**
   - If any step fails, stop and do not continue to later steps.
   - If the commit exists but the push failed: report it, and leave the local commit and tag in place so the user can retry. Do not force-push.
   - If the push succeeded but the GitHub release failed: retry the release once. If it still fails, report the exact error and leave the tag. Do not delete anything remote.
   - Never delete or move a published tag, force-push, or rewrite history without the user's explicit instruction.
   - Local-only cleanup is allowed with the user's agreement: delete an unpushed tag with `git tag -d vx.y.z`, and undo an unpushed commit with `git reset --soft HEAD~1`.
   - Always state what has been done and what has not.
8. **Verify and report**
   - Confirm the tag, the release body and the version strings all show `x.y.z`.
   - Tell the user the version, the commit hash and the release URL.

## 2. This file is not shipped
- HACS installs only `custom_components/metlink_explorer/`, so root files like this one are never delivered to users. `hacs.json` and `manifest.json` have no exclude option. Do not add one.
- Keep this file in the repository root. Never place it inside `custom_components/`.


### 3.1 Design principles
- Fetch each upstream feed once per interval, share the result, and filter late.
- Static data lives in SQLite on disk, never in memory.
- Live data is small, bounded, and replaced, with no history.
- Each data source has its own task, state and backoff. One failing source never affects another.
- Nothing blocks the event loop. Long-lived work uses Home Assistant tracked background tasks, never bare `asyncio.create_task`.

### 3.2 Integration vs card
- The integration is a data service. The card is the UI and holds the user's route and stop selections.
- The config flow asks only for the Metlink API key and the optional AISStream key (and optionally which modes to enable). There is no per-route or per-stop options flow.
- Entities are diagnostics only: feed status, last update, AIS connection state. No per-route or per-stop entities. No automation support (by design).
- Home Assistant only. No separate HTTP interface for third parties.

### 3.3 Modes
- Bus, Train and Ferry modules, each with its own schedule and error handling.
- Bus and Train live tracking come from Metlink GTFS-RT. Ferry live tracking comes from AISStream, matched to the schedule through the MMSI map.
- All modes share the same core layers for the Metlink client, static GTFS, realtime feeds and AIS.

### 3.4 Layout
```
custom_components/metlink_explorer/
  __init__.py  config_flow.py  const.py
  core/   http.py  store.py  static_sync.py  realtime.py  ais.py  models.py
  modes/  base.py  bus.py  train.py  ferry.py
  sensor.py (diagnostics)  websocket_api.py
  frontend/  (cards)
```

### 3.5 Static data
- Download all GTFS static data (routes, stops, trips, shapes, stop_times) into SQLite in the background, in an executor, with batched inserts.
- The sync is resumable and skips unchanged feeds via ETag or Last-Modified. Refresh daily.
- Disk size and sync time do not matter. Memory does.
- Use indexes (for example `stop_times(stop_id, departure_time)` and `trips(route_id)`), WAL mode and a capped page cache.

### 3.6 Realtime
- One task per feed (vehicle positions, trip updates, alerts). Decode in an executor and keep only a compact latest snapshot.
- Data updates every 4-8 seconds for vehicles, so poll vehicles at 10s, trip updates at 30s, and alerts every 3 minutes while a card is subscribed, and stop when nobody is subscribed. The first subscriber triggers an immediate fetch.
- Alerts every 2-5 minutes. Honour `Retry-After` and use exponential backoff with jitter on 429.
- Push only changed vehicles to subscribers.

### 3.7 AIS
- Exactly one websocket, managed by a singleton `AisStreamManager`, reference-counted and run as an HA background task so it can never leak.
- Reconnect with exponential backoff and jitter (1 min up to 15-30 min). Stop on 401/403. Never raise into callers.
- Keep only the last position per tracked MMSI, with an age flag. Discard other vessels immediately.
- Push updates to subscribers every 5-10 seconds, changed vessels only. Ferries fall back to scheduled data if AIS is down.
- Known bug in v1.x: every `MetlinkApiClient` starts its own AIS task and failed setups leak them. The singleton manager fixes this.

### 3.8 Websocket API (authenticated, via `hass.callWS` and subscriptions)
- `metlink/routes`, `metlink/stops`: searchable lists with a `mode` filter
- `metlink/shape`: route GPS path
- `metlink/stop_departures`: scheduled times merged with live trip updates
- `metlink/subscribe_vehicles` (`route_ids`) and `metlink/subscribe_departures` (`stop_ids`)
- `metlink/status`: feed health, so cards can show stale or offline states
- Register every subscription in `connection.subscriptions` so Home Assistant cleans it up.
- Cards fetch static data (shapes, lists) once and cache it. They resubscribe on reconnect.

### 3.9 Build order
1. Scaffold, `core/http.py` (rate limit and backoff) and `core/store.py`, with tests.
2. `core/static_sync.py`.
3. `core/realtime.py` and the websocket commands for routes, stops, shapes and departures.
4. Vehicle subscriptions for bus and train.
5. `core/ais.py` and the ferry merge.
6. Rewrite the cards on the websocket client.
7. Docs, then release 2.0.0 (using the release procedure in section 1).

### 3.10 Post-2.2 patch backlog (outlines only)
Each remaining item needs a discussion with the user before implementation. Do not implement until the user says so.

Done or superseded (as of 2.9.0): items 1-4, 6-10 and 13 were built in 2.x. Item 5 is superseded by the departure board grouped by stop. Item 12 is superseded by the alert bar with a pop-down.

Still open:
- Item 11: stop search lists all stops, sortable by number, suburb, route or alphabetically. Possible extension: group bus hubs (for example Courtenay Place), since the Metlink feed only has train-station parents.


## 4. Secrets
- Never write API keys, tokens or passwords into source, tests, logs, docs, the changelog or commit messages. Use placeholders such as `YOUR_API_KEY`.
- Do not commit debug logs, pasted logs, `.env` files or HA config exports without checking them for keys first.
- If a secret is found in already-committed history, stop and tell the user. The key must be revoked and rotated.

## 5. General working rules
- Make small, focused changes. Run the relevant tests or lint after each change.
- Do not edit generated or snapshot files. Update README and docs when behaviour changes.
- On Windows, use backslash paths in shell commands.
