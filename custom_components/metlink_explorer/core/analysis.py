"""Pure functions that derive inbound/outbound and stop pairs from static GTFS."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..const import (
    CBD_ANCHORS,
    CBD_RADIUS_M,
    DIRECTION_LOOKAHEAD_M,
    DIRECTION_MIN_DELTA_M,
    HUB_RADIUS_M,
    PAIR_MAX_DISTANCE_M,
    PAIR_MAX_DISTANCE_STRONG_M,
    PAIR_MIN_SCORE,
    REGIONAL_HUBS,
)

EARTH_RADIUS_M = 6371000.0

_PAREN = re.compile(r"\([^)]*\)")
_STOP_SUFFIX = re.compile(r"\s*-\s*(stop|platform|bay)\s+\w+\s*$")
_POSITION_WORDS = re.compile(r"\s+(near|opposite|opp|outside|nr)\b.*$")
_SPACES = re.compile(r"\s+")


@dataclass(slots=True, frozen=True)
class StopPoint:
    stop_id: str
    name: str
    lat: float
    lon: float
    parent: str = ""


@dataclass(slots=True)
class RouteDirection:
    """The dominant stop sequence of one route direction."""

    direction_id: int
    stop_ids: Sequence[str]


@dataclass(slots=True)
class DirectionResult:
    method: str
    confidence: float
    attractors: tuple


@dataclass(slots=True)
class PairResult:
    route_id: str
    stop_id: str
    paired_stop_id: str
    score: float
    distance_m: float
    reasons: str = ""
    extra: dict = field(default_factory=dict)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def name_root(name: str) -> str:
    """Normalise a stop name so both sides of the road compare equal."""
    text = _PAREN.sub("", name.lower())
    text = _STOP_SUFFIX.sub("", text)
    text = _POSITION_WORDS.sub("", text)
    return _SPACES.sub(" ", text).strip(" -")


def street_part(root: str) -> str:
    return re.split(r"\s+(?:at|-)\s+", root, maxsplit=1)[0].strip()


def _nearest(lat: float, lon: float, anchors) -> float:
    return min(haversine_m(lat, lon, a_lat, a_lon) for _, a_lat, a_lon in anchors)


def choose_attractors(
    directions: Sequence[RouteDirection],
    stops: Mapping[str, StopPoint],
    stop_route_counts: Mapping[str, int],
    *,
    cbd_anchors=CBD_ANCHORS,
    hubs=REGIONAL_HUBS,
    cbd_radius_m: float = CBD_RADIUS_M,
    hub_radius_m: float = HUB_RADIUS_M,
) -> DirectionResult:
    """Pick the points a route's "inbound" travel is measured towards.

    1. CBD anchors, when any stop is within `cbd_radius_m` of one.
    2. The regional hubs the route actually touches.
    3. The route's busiest shared stop (the stop served by the most routes).
    4. Nothing: directions stay unknown.
    """
    points = [stops[s] for d in directions for s in d.stop_ids if s in stops]
    if not points:
        return DirectionResult("default", 0.0, ())

    if any(_nearest(p.lat, p.lon, cbd_anchors) <= cbd_radius_m for p in points):
        return DirectionResult("cbd", 0.95, tuple(cbd_anchors))

    touched = tuple(
        hub for hub in hubs if any(haversine_m(p.lat, p.lon, hub[1], hub[2]) <= hub_radius_m for p in points)
    )
    if touched:
        return DirectionResult("hub", 0.8, touched)

    shared = [p for p in points if stop_route_counts.get(p.stop_id, 0) >= 2]
    if shared:
        busiest = max(shared, key=lambda p: stop_route_counts.get(p.stop_id, 0))
        return DirectionResult("busiest", 0.6, ((busiest.name, busiest.lat, busiest.lon),))

    return DirectionResult("default", 0.0, ())


def label_pattern_directions(
    stop_ids: Sequence[str],
    stops: Mapping[str, StopPoint],
    attractors,
    *,
    lookahead_m: float = DIRECTION_LOOKAHEAD_M,
    min_delta_m: float = DIRECTION_MIN_DELTA_M,
) -> list[int | None]:
    """Label each stop of one pattern 1 (towards the attractors) or 0 (away).

    A stop is labelled by comparing its distance to the nearest attractor with
    that of the point about `lookahead_m` further along the pattern. Stops where
    the change is small take the previous label, and leading ones the next.
    Unknown stops and routes without attractors return None.
    """
    labels: list[int | None] = [None] * len(stop_ids)
    if not attractors:
        return labels

    known = [(i, stops[s]) for i, s in enumerate(stop_ids) if s in stops]
    if len(known) < 2:
        return labels

    dist = [_nearest(p.lat, p.lon, attractors) for _, p in known]
    along = [0.0]
    for k in range(1, len(known)):
        a, b = known[k - 1][1], known[k][1]
        along.append(along[-1] + haversine_m(a.lat, a.lon, b.lat, b.lon))

    last = len(known) - 1
    ahead = 1
    raw: list[int | None] = []
    for k in range(len(known)):
        ahead = max(ahead, k + 1)
        while ahead < last and along[ahead] - along[k] < lookahead_m:
            ahead += 1
        target = min(ahead, last)
        delta = dist[k] - dist[target] if target != k else 0.0
        raw.append(1 if delta >= min_delta_m else 0 if delta <= -min_delta_m else None)

    current: int | None = None
    filled: list[int | None] = []
    for value in raw:
        current = value if value is not None else current
        filled.append(current)
    first = next((v for v in filled if v is not None), None)
    filled = [v if v is not None else first for v in filled]
    for (index, _), value in zip(known, filled):
        labels[index] = value
    return labels


def _score_pair(
    a: StopPoint,
    b: StopPoint,
    pos_a: float,
    pos_b: float,
    distance: float,
) -> tuple[float, list[str], bool]:
    """Score a candidate pair. Returns (score, reasons, strong)."""
    score = 0.0
    reasons: list[str] = []
    strong = False

    if a.parent and a.parent == b.parent:
        score += 0.5
        reasons.append("parent")
        strong = True

    root_a, root_b = name_root(a.name), name_root(b.name)
    if root_a and root_a == root_b:
        score += 0.35
        reasons.append("name")
        strong = True
    elif street_part(root_a) and street_part(root_a) == street_part(root_b):
        score += 0.15
        reasons.append("street")

    # Positions are fractions through each direction's stop list.
    mirror = abs(pos_a + pos_b - 1.0)
    if mirror <= 0.1:
        score += 0.25
        reasons.append("mirror")
    elif mirror <= 0.2:
        score += 0.1
        reasons.append("mirror~")

    # Metlink numbers the opposite side of a road 1000 higher or lower (6931/7931).
    if (
        a.stop_id.isdigit()
        and b.stop_id.isdigit()
        and abs(int(a.stop_id) - int(b.stop_id)) == 1000
        and root_a == root_b
    ):
        score += 0.2
        reasons.append("id1000")

    if distance <= 30:
        score += 0.2
        reasons.append("<=30m")
    elif distance <= 60:
        score += 0.15
        reasons.append("<=60m")
    elif distance <= 100:
        score += 0.05
        reasons.append("<=100m")

    return score, reasons, strong and mirror <= 0.2


def pair_route_stops(
    route_id: str,
    directions: Sequence[RouteDirection],
    stops: Mapping[str, StopPoint],
    *,
    max_distance_m: float = PAIR_MAX_DISTANCE_M,
    max_distance_strong_m: float = PAIR_MAX_DISTANCE_STRONG_M,
    min_score: float = PAIR_MIN_SCORE,
) -> list[PairResult]:
    """Pair stops serving opposite directions of one route.

    Termini never pair. A pair is kept only when each stop's best candidate is
    the other (mutual), so a wrong pair is less likely than a missed one.
    """
    by_dir = {d.direction_id: d for d in directions if len(d.stop_ids) >= 3}
    if len(by_dir) < 2:
        return []
    dir_a, dir_b = sorted(by_dir)[:2]

    def interior(direction: RouteDirection):
        ids = list(direction.stop_ids)
        n = len(ids)
        for index, sid in enumerate(ids):
            if index in (0, n - 1) or sid not in stops:
                continue
            yield sid, index / (n - 1)

    list_a = list(interior(by_dir[dir_a]))
    list_b = list(interior(by_dir[dir_b]))

    candidates: dict[tuple[str, str], tuple[float, float, list[str]]] = {}
    for sid_a, pos_a in list_a:
        for sid_b, pos_b in list_b:
            if sid_a == sid_b:
                continue
            a, b = stops[sid_a], stops[sid_b]
            distance = haversine_m(a.lat, a.lon, b.lat, b.lon)
            if distance > max_distance_strong_m:
                continue
            score, reasons, strong = _score_pair(a, b, pos_a, pos_b, distance)
            if distance > max_distance_m and not strong:
                continue
            if score < min_score:
                continue
            candidates[(sid_a, sid_b)] = (score, distance, reasons)

    best_for_a: dict[str, tuple[float, float, str]] = {}
    best_for_b: dict[str, tuple[float, float, str]] = {}
    for (sid_a, sid_b), (score, distance, _) in candidates.items():
        cur = best_for_a.get(sid_a)
        if cur is None or (score, -distance) > (cur[0], -cur[1]):
            best_for_a[sid_a] = (score, distance, sid_b)
        cur = best_for_b.get(sid_b)
        if cur is None or (score, -distance) > (cur[0], -cur[1]):
            best_for_b[sid_b] = (score, distance, sid_a)

    results: list[PairResult] = []
    for sid_a, (score, distance, sid_b) in best_for_a.items():
        if best_for_b.get(sid_b, (0, 0, ""))[2] != sid_a:
            continue
        reasons = ",".join(candidates[(sid_a, sid_b)][2])
        results.append(PairResult(route_id, sid_a, sid_b, round(score, 3), round(distance, 1), reasons))
        results.append(PairResult(route_id, sid_b, sid_a, round(score, 3), round(distance, 1), reasons))
    return results


def group_pairs(pairs: Sequence[PairResult]) -> dict[str, str]:
    """Greedily build groups of at most two stops from per-route pairs.

    Pair scores are summed across routes; the highest totals are matched first
    and every stop joins at most one group. Returns stop_id -> group_id, where
    group_id is the lower stop_id of the two.
    """
    totals: dict[tuple[str, str], float] = {}
    for p in pairs:
        key = tuple(sorted((p.stop_id, p.paired_stop_id)))
        totals[key] = totals.get(key, 0.0) + p.score / 2  # each pair appears twice

    groups: dict[str, str] = {}
    for (x, y), _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        if x in groups or y in groups:
            continue
        groups[x] = groups[y] = x
    return groups
