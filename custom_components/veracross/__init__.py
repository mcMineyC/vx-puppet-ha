"""The Veracross Grades integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SCHOOL, DATA_MANAGER, DOMAIN
from .manager import VeracrossManager

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = VeracrossManager(
        hass=hass,
        entry_id=entry.entry_id,
        school=entry.data[CONF_SCHOOL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_MANAGER: manager}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # kick off one fetch at startup so entities aren't empty until someone
    # presses the button
    async def _initial_fetch() -> None:
        try:
            await manager.async_fetch_grades()
        except Exception:  # noqa: BLE001 - logged inside manager, don't crash startup
            pass

    hass.async_create_task(_initial_fetch())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
