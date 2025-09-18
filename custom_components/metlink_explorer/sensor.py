import logging
_LOGGER = logging.getLogger(__name__)

async def async_update(self):
    # 1. Get all trips for the route
    trips = await self._client.get_trips(self._route_id)
    if not trips:
        self._extra_state_attributes["route_stops"] = []
        self._state = 0
        return

    # 2. Pick the first trip (or improve logic to select the right one)
    trip_id = trips[0]["trip_id"]

    # 3. Get stop times for the trip (ordered)
    stop_times = await self._client.get_stop_times(trip_id)
    stop_ids = [st["stop_id"] for st in stop_times]

    # 4. Get stop details
    stops = await self._client.get_stops_by_ids(stop_ids)
    stop_lookup = {stop["stop_id"]: stop for stop in stops}

    # 5. Get real-time predictions for each stop
    predictions = await self._client.get_departure_predictions(self._route_id)
    pred_lookup = {}
    for pred in predictions:
        pred_lookup.setdefault(pred["stop_id"], []).append(pred)

    # 6. Get alerts and trip updates
    alerts = await self._client.get_service_alerts(self._route_id)
    trip_updates = await self._client.get_trip_updates(self._route_id)
    cancellations = await self._client.get_trip_cancellations(self._route_id)

    # 7. Build the route info
    route_stops = []
    for st in stop_times:
        stop_id = st["stop_id"]
        stop_info = stop_lookup.get(stop_id, {})
        scheduled_time = st.get("departure_time")
        realtime = pred_lookup.get(stop_id, [])
        route_stops.append({
            "stop_id": stop_id,
            "stop_name": stop_info.get("stop_name"),
            "scheduled_departure": scheduled_time,
            "realtime_predictions": realtime,
        })

    self._extra_state_attributes["route_stops"] = route_stops
    self._extra_state_attributes["alerts"] = alerts
    self._extra_state_attributes["trip_updates"] = trip_updates
    self._extra_state_attributes["cancellations"] = cancellations

    # Set state to number of stops or next departure, as you wish
    self._state = len(route_stops)
    _LOGGER.info("Route stops: %s", route_stops)