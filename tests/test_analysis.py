"""Tests for direction detection, name normalisation and stop pairing."""
from custom_components.metlink_explorer.core.analysis import (
    PairResult,
    RouteDirection,
    StopPoint,
    choose_attractors,
    group_pairs,
    haversine_m,
    label_pattern_directions,
    name_root,
    pair_route_stops,
)


def pts(*items):
    return {i[0]: StopPoint(*i) for i in items}


def test_haversine_known_distance():
    assert 110000 < haversine_m(0, 0, 1, 0) < 112000


def test_name_root_ignores_position_words_and_stop_letters():
    assert name_root("Buckley Road (near 108)") == "buckley road"
    assert name_root("Thorndon Quay near 125") == "thorndon quay"
    assert name_root("Manners Street at Cuba Street - Stop A") == name_root(
        "Manners Street at Cuba Street - Stop B"
    )
    assert name_root("Thorndon Quay opposite 9") == "thorndon quay"


FAR = (-41.20, 174.90)
CBD = (-41.2782, 174.7800)


def line(prefix, lat0, lat1, n):
    """n stops on a north-south line, evenly spaced."""
    return {
        f"{prefix}{k}": StopPoint(f"{prefix}{k}", f"{prefix} {k}", lat0 + (lat1 - lat0) * k / (n - 1), 174.78)
        for k in range(n)
    }


def test_labels_towards_and_away_from_cbd():
    stops = line("S", -41.20, -41.2782, 9)  # north to Wellington Station
    ids = list(stops)
    attractors = choose_attractors([RouteDirection(1, ids)], stops, {}).attractors
    assert label_pattern_directions(ids, stops, attractors) == [1] * 9
    assert label_pattern_directions(ids[::-1], stops, attractors) == [0] * 9


def test_cross_town_route_flips_after_passing_the_cbd():
    north = line("N", -41.24, -41.2782, 6)
    south = line("M", -41.2782, -41.32, 6)
    stops = {**north, **south}
    ids = list(north) + list(south)[1:]
    result = choose_attractors([RouteDirection(0, ids)], stops, {})
    assert result.method == "cbd"
    labels = label_pattern_directions(ids, stops, result.attractors)
    assert labels[0] == 1 and labels[-1] == 0
    # Middle stops may be pulled by a nearer secondary anchor; the ends must be firm.
    assert labels[:5] == [1] * 5 and labels[-4:] == [0] * 4


def test_loop_flips_halfway():
    out = line("O", -41.2782, -41.20, 6)
    back = line("B", -41.20, -41.2782, 6)
    stops = {**out, **back}
    ids = list(out) + list(back)[1:]
    labels = label_pattern_directions(ids, stops, choose_attractors([RouteDirection(0, ids)], stops, {}).attractors)
    assert labels[1] == 0 and labels[-2] == 1


def test_hub_used_when_route_avoids_cbd():
    queensgate = (-41.2103, 174.9049)
    stops = {
        "home": StopPoint("home", "Suburb", -41.3500, 174.9500),
        "mid": StopPoint("mid", "Mid", -41.28, 174.93),
        "hub": StopPoint("hub", "Hub", *queensgate),
    }
    ids = ["home", "mid", "hub"]
    result = choose_attractors([RouteDirection(0, ids)], stops, {})
    assert result.method == "hub"
    assert label_pattern_directions(ids, stops, result.attractors) == [1, 1, 1]
    assert label_pattern_directions(ids[::-1], stops, result.attractors) == [0, 0, 0]


def test_busiest_shared_stop_used_for_remote_routes():
    stops = line("R", -41.0, -40.9, 6)
    ids = list(stops)
    # The far end is a shared interchange served by several routes.
    result = choose_attractors([RouteDirection(0, ids)], stops, {"R5": 4})
    assert result.method == "busiest"
    labels = label_pattern_directions(ids, stops, result.attractors)
    assert labels[0] == 1 and labels[-1] == 1


def test_no_attractor_gives_unknown_labels():
    stops = line("Q", -41.0, -40.95, 4)
    result = choose_attractors([RouteDirection(0, list(stops))], stops, {})
    assert result.method == "default" and result.confidence == 0
    assert label_pattern_directions(list(stops), stops, result.attractors) == [None] * 4


def test_missing_stops_are_unknown_but_do_not_break_labelling():
    stops = line("S", -41.20, -41.2782, 5)
    ids = ["S0", "ghost", "S1", "S2", "S3", "S4"]
    labels = label_pattern_directions(ids, stops, choose_attractors([RouteDirection(0, list(stops))], stops, {}).attractors)
    assert labels[1] is None and labels[0] == 1 and labels[-1] == 1


def _road(k_count=5, offset=0.0002, name_b=None):
    stops = {}
    for k in range(k_count):
        lat = -41.22 - 0.0125 * k
        stops[f"A{k}"] = StopPoint(f"A{k}", f"Main Road (near {k})", lat, 174.80)
        stops[f"B{k}"] = StopPoint(f"B{k}", name_b or f"Main Road (opposite {k})", lat, 174.80 + offset)
    a = [f"A{k}" for k in range(k_count)]
    b = [f"B{k}" for k in range(k_count - 1, -1, -1)]
    return stops, [RouteDirection(1, a), RouteDirection(0, b)]


def test_pairs_opposite_stops_and_skips_termini():
    stops, dirs = _road()
    pairs = pair_route_stops("R", dirs, stops)
    mapping = {p.stop_id: p.paired_stop_id for p in pairs}
    assert mapping == {"A1": "B1", "B1": "A1", "A2": "B2", "B2": "A2", "A3": "B3", "B3": "A3"}
    assert all(p.reasons and p.score >= 0.5 for p in pairs)


def test_far_apart_stops_do_not_pair():
    stops, dirs = _road(offset=0.003)  # about 260 m across
    assert pair_route_stops("R", dirs, stops) == []


def test_wide_road_pairs_only_with_strong_signals():
    # about 100 m apart: beyond the normal gate, allowed because names and position agree.
    stops, dirs = _road(offset=0.0012)
    assert len(pair_route_stops("R", dirs, stops)) == 6
    # Same distance but unrelated names: rejected.
    stops2, dirs2 = _road(offset=0.0012)
    for sid in list(stops2):
        if sid.startswith("B"):
            stops2[sid] = StopPoint(sid, f"Other Place {sid}", stops2[sid].lat, stops2[sid].lon)
    assert pair_route_stops("R", dirs2, stops2) == []


def test_parent_station_pairs():
    stops, dirs = _road(offset=0.0012)
    for sid in ("A2", "B2"):
        p = stops[sid]
        stops[sid] = StopPoint(sid, "Station " + sid, p.lat, p.lon, "PARENT")
    pairs = {p.stop_id: p.paired_stop_id for p in pair_route_stops("R", dirs, stops)}
    assert pairs["A2"] == "B2"


def test_id_gap_of_1000_boosts_pair_score():
    def pair_score(id_a, id_b):
        stops = {}
        for k in range(5):
            lat = -41.22 - 0.0125 * k
            stops[f"{id_a}{k}"] = StopPoint(f"{id_a}{k}", "Hill Road", lat, 174.80)
            stops[f"{id_b}{k}"] = StopPoint(f"{id_b}{k}", "Hill Road", lat, 174.8002)
        dirs = [
            RouteDirection(1, [f"{id_a}{k}" for k in range(5)]),
            RouteDirection(0, [f"{id_b}{k}" for k in range(4, -1, -1)]),
        ]
        return pair_route_stops("R", dirs, stops)[0]

    # Numeric ids differing by exactly 1000 (6931 / 7931 style).
    stops = {}
    for k in range(5):
        lat = -41.22 - 0.0125 * k
        stops[str(6000 + k)] = StopPoint(str(6000 + k), "Hill Road", lat, 174.80)
        stops[str(7000 + k)] = StopPoint(str(7000 + k), "Hill Road", lat, 174.8002)
    dirs = [
        RouteDirection(1, [str(6000 + k) for k in range(5)]),
        RouteDirection(0, [str(7000 + k) for k in range(4, -1, -1)]),
    ]
    boosted = pair_route_stops("R", dirs, stops)
    assert boosted and all("id1000" in p.reasons for p in boosted)
    assert "id1000" not in pair_score("X", "Y").reasons


def test_group_pairs_matches_each_stop_once():
    pairs = [
        PairResult("R1", "A", "B", 0.9, 10), PairResult("R1", "B", "A", 0.9, 10),
        PairResult("R2", "A", "C", 0.6, 10), PairResult("R2", "C", "A", 0.6, 10),
    ]
    groups = group_pairs(pairs)
    assert groups == {"A": "A", "B": "A"}
