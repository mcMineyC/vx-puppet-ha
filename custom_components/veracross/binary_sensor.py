"""Binary sensor reflecting whether a grade fetch is in progress."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SCHOOL, DATA_MANAGER, DOMAIN, SIGNAL_UPDATING_STATE
from .manager import VeracrossManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: VeracrossManager = hass.data[DOMAIN][entry.entry_id][DATA_MANAGER]
    async_add_entities([VeracrossUpdatingBinarySensor(entry, manager)])


class VeracrossUpdatingBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Updating"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, manager: VeracrossManager) -> None:
        self._entry = entry
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_updating"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Veracross ({entry.data[CONF_SCHOOL]})",
            manufacturer="Veracross (unofficial)",
        )

    @property
    def is_on(self) -> bool:
        return self._manager.updating

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATING_STATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, _value: bool) -> None:
        self.async_write_ha_state()
