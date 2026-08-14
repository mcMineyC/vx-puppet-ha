"""Button to trigger a grade fetch."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SCHOOL, DATA_MANAGER, DOMAIN
from .manager import VeracrossError, VeracrossManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: VeracrossManager = hass.data[DOMAIN][entry.entry_id][DATA_MANAGER]
    async_add_entities([VeracrossUpdateButton(entry, manager)])


class VeracrossUpdateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Refresh All Grades"
    _attr_icon = "mdi:refresh"

    def __init__(self, entry: ConfigEntry, manager: VeracrossManager) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_refresh_all_button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Veracross ({entry.data[CONF_SCHOOL]})",
            manufacturer="Veracross (unofficial)",
        )

    async def async_press(self) -> None:
        try:
            await self._manager.async_fetch_grades()
        except VeracrossError as err:
            _LOGGER.error("Veracross grade fetch failed: %s", err)
