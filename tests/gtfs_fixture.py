"""Builds a small synthetic GTFS zip for tests."""
import io
import zipfile

FAR_LAT = -41.22
STEP = 0.0125
LON = 174.80
OFFSET = 0.0002  # about 17 m across the road


def _csv(header, rows):
    return ",".join(header) + "\n" + "\n".join(",".join(str(c) for c in r) for r in rows) + "\n"


def build_zip(*, feed_version="v1", patterns=True, extra_stop_name="Elsewhere") -> bytes:
    stops = []
    for k in range(5):
        lat = FAR_LAT - STEP * k
        stops.append((f"A{k}", f"Main Road (near {k})", lat, LON, "", 0))
        stops.append((f"B{k}", f"Main Road (opposite {k})", lat, LON + OFFSET, "", 0))
    stops.append(("Z1", extra_stop_name, -41.40, 175.0, "", 0))

    routes = [
        ("R1", "AG", "1", "Far to City", "", 3, "", "ffffff", "000000", 1),
        ("R2", "AG", "S2", "School", "", 712, "", "ffffff", "000000", 2),
        ("R3", "AG", "F", "Ferry", "", 4, "", "ffffff", "000000", 3),
    ]
    trips = [
        ("R1", "wk", "T_in_1", "City", 1, "", "SH1"),
        ("R1", "wk", "T_in_2", "City", 1, "", "SH1"),
        ("R1", "wk", "T_out_1", "Far", 0, "", "SH0"),
        ("R2", "wk", "T_sch", "School", 1, "", "SH1"),
    ]
    inbound_ids = [f"A{k}" for k in range(5)]
    outbound_ids = [f"B{k}" for k in range(4, -1, -1)]

    def times(trip_id, stop_ids, start):
        return [
            (trip_id, f"{(start + i * 60) // 3600:02d}:{(start + i * 60) % 3600 // 60:02d}:00",
             f"{(start + i * 60) // 3600:02d}:{(start + i * 60) % 3600 // 60:02d}:00",
             sid, i, "", 0, 0, "", 1)
            for i, sid in enumerate(stop_ids)
        ]

    stop_times = (
        times("T_in_1", inbound_ids, 8 * 3600)
        + times("T_in_2", inbound_ids, 9 * 3600)
        + times("T_out_1", outbound_ids, 8 * 3600)
        + times("T_sch", inbound_ids, 25 * 3600 - 30 * 60)
    )
    shapes = [("SH1", -41.22, 174.8, 0, 0), ("SH1", -41.27, 174.8, 1, 5000),
              ("SH0", -41.27, 174.8, 0, 0), ("SH0", -41.22, 174.8, 1, 5000)]

    files = {
        "agency.txt": _csv(["agency_id", "agency_name"], [("AG", "Agency")]),
        "feed_info.txt": _csv(["feed_publisher_name", "feed_version"], [("Pub", feed_version)]),
        "routes.txt": _csv(
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_desc",
             "route_type", "route_url", "route_color", "route_text_color", "route_sort_order"], routes),
        "stops.txt": _csv(
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "parent_station", "location_type"], stops),
        "trips.txt": _csv(
            ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "block_id", "shape_id"], trips),
        "stop_times.txt": _csv(
            ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "stop_headsign",
             "pickup_type", "drop_off_type", "shape_dist_traveled", "timepoint"], stop_times),
        "shapes.txt": _csv(
            ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled"], shapes),
        "calendar.txt": _csv(
            ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
             "start_date", "end_date"], [("wk", 1, 1, 1, 1, 1, 0, 0, 20260101, 20261231)]),
        "calendar_dates.txt": _csv(["service_id", "date", "exception_type"], [("wk", 20260105, 2)]),
    }
    if patterns:
        files["stop_patterns.txt"] = _csv(
            ["stop_pattern_id", "stop_id", "stop_sequence", "timepoint"],
            [("P_in", sid, i, 0) for i, sid in enumerate(inbound_ids)]
            + [("P_out", sid, i, 0) for i, sid in enumerate(outbound_ids)],
        )
        files["stop_pattern_trips.txt"] = _csv(
            ["stop_pattern_id", "trip_id", "trip_sequence"],
            [("P_in", "T_in_1", 1), ("P_in", "T_in_2", 2), ("P_out", "T_out_1", 1), ("P_in", "T_sch", 3)],
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()
