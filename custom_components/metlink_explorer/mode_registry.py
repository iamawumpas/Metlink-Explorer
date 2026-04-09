"""Helpers for normalized mode grouping and route extraction."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_ROUTE_DESC,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    CONF_ROUTES,
    CONF_TRANSPORTATION_TYPE,
    DOMAIN,
)


def normalize_transportation_type(value: Any) -> int:
    """Normalize transportation type to int for stable comparisons."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def entry_routes_from_data(data: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return normalized routes list from entry data with legacy fallback."""
    routes = data.get(CONF_ROUTES)
    normalized: list[dict[str, str]] = []

    if isinstance(routes, list) and routes:
        for route in routes:
            if not isinstance(route, Mapping):
                continue
            route_id = str(route.get(CONF_ROUTE_ID, "")).strip()
            if not route_id:
                continue
            normalized.append(
                {
                    CONF_ROUTE_ID: route_id,
                    CONF_ROUTE_SHORT_NAME: route.get(CONF_ROUTE_SHORT_NAME),
                    CONF_ROUTE_LONG_NAME: route.get(CONF_ROUTE_LONG_NAME),
                    CONF_ROUTE_DESC: route.get(CONF_ROUTE_DESC, ""),
                }
            )
        if normalized:
            return normalized

    legacy_route_id = str(data.get(CONF_ROUTE_ID, "")).strip()
    if legacy_route_id:
        return [
            {
                CONF_ROUTE_ID: legacy_route_id,
                CONF_ROUTE_SHORT_NAME: data.get(CONF_ROUTE_SHORT_NAME),
                CONF_ROUTE_LONG_NAME: data.get(CONF_ROUTE_LONG_NAME),
                CONF_ROUTE_DESC: data.get(CONF_ROUTE_DESC, ""),
            }
        ]

    return []


def entry_routes(entry: ConfigEntry) -> list[dict[str, str]]:
    """Return normalized routes list from a config entry."""
    return entry_routes_from_data(entry.data)


def same_mode_entries(
    hass: HomeAssistant,
    api_key: str | None,
    transportation_type: Any,
) -> list[ConfigEntry]:
    """Return entries for the same API key + transportation type."""
    normalized_type = normalize_transportation_type(transportation_type)
    return sorted(
        [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_API_KEY) == api_key
            and normalize_transportation_type(entry.data.get(CONF_TRANSPORTATION_TYPE)) == normalized_type
        ],
        key=lambda entry: entry.entry_id,
    )


def merged_routes(entries: list[ConfigEntry]) -> list[dict[str, str]]:
    """Merge and deduplicate routes from a list of entries by route_id."""
    result: list[dict[str, str]] = []
    seen_route_ids: set[str] = set()

    for entry in entries:
        for route in entry_routes(entry):
            route_id = route[CONF_ROUTE_ID]
            if route_id in seen_route_ids:
                continue
            seen_route_ids.add(route_id)
            result.append(route)

    return result


def is_mode_leader(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Return True when this entry is the deterministic leader for its mode."""
    group = same_mode_entries(
        hass,
        entry.data.get(CONF_API_KEY),
        entry.data.get(CONF_TRANSPORTATION_TYPE),
    )
    if not group:
        return True
    return entry.entry_id == group[0].entry_id
