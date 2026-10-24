"""Select platform for Metlink Explorer."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ACTIVE_DIRECTION,
    CONF_ROUTE_DESC,
    CONF_ROUTE_ID,
    CONF_ROUTE_LONG_NAME,
    CONF_ROUTE_SHORT_NAME,
    DEFAULT_ACTIVE_DIRECTION,
    DOMAIN,
)
from .mode_registry import entry_routes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up direction selector entity."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = runtime.get("coordinators", {})

    routes = entry_routes(config_entry)

    entities: list[MetlinkDirectionSelect] = []
    for route in routes:
        route_id = str(route.get(CONF_ROUTE_ID))
        if not route_id:
            continue
        coordinator = coordinators.get(route_id) or runtime.get("coordinator")
        if not coordinator:
            continue

        entities.append(
            MetlinkDirectionSelect(
                coordinator,
                config_entry,
                route_id,
                route.get(CONF_ROUTE_SHORT_NAME, "Unknown"),
                route.get(CONF_ROUTE_LONG_NAME, "Unknown Route"),
                route.get(CONF_ROUTE_DESC, ""),
            )
        )

    async_add_entities(entities)


class MetlinkDirectionSelect(CoordinatorEntity, SelectEntity):
    """Select active direction for route-centric sensor views."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        route_id: str,
        route_short_name: str,
        route_long_name: str,
        route_desc: str,
    ) -> None:
        """Initialize direction select."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._route_id = route_id
        self._route_short_name = route_short_name
        self._direction_0 = route_desc or route_long_name
        self._direction_1 = route_long_name

        self._attr_name = f"{route_short_name} :: Active Direction"
        self._attr_unique_id = f"{DOMAIN}_{route_id}_active_direction"
        self._attr_options = [self._direction_0, self._direction_1]

    @property
    def current_option(self) -> str | None:
        """Return current selected direction option."""
        active_direction = int(self._config_entry.options.get(CONF_ACTIVE_DIRECTION, DEFAULT_ACTIVE_DIRECTION))
        return self._direction_0 if active_direction == 0 else self._direction_1

    async def async_select_option(self, option: str) -> None:
        """Change active direction and persist in config entry options."""
        if option not in self.options:
            return

        new_direction = 0 if option == self._direction_0 else 1
        new_options = dict(self._config_entry.options)
        new_options[CONF_ACTIVE_DIRECTION] = new_direction

        self.hass.config_entries.async_update_entry(self._config_entry, options=new_options)
        self.async_write_ha_state()
