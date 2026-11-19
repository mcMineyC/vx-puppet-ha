"""The Veracross Grades integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SCHOOL, DATA_MANAGER, DOMAIN, SERVICE_REFRESH
from .manager import VeracrossError, VeracrossManager

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def _refresh(call: ServiceCall) -> ServiceResponse:
        managers: dict[str, VeracrossManager] = {
            entry_id: data[DATA_MANAGER]
            for entry_id, data in hass.data.get(DOMAIN, {}).items()
        }
        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if entry_id is None:
            if len(managers) != 1:
                raise ServiceValidationError(
                    "config_entry_id is required when zero or several Veracross accounts are set up"
                )
            entry_id = next(iter(managers))
        manager = managers.get(entry_id)
        if manager is None:
            raise ServiceValidationError(f"No loaded Veracross entry {entry_id}")

        try:
            await manager.async_fetch_grades()
        except VeracrossError as err:
            raise HomeAssistantError(f"Veracross fetch failed: {err}") from err

        if not call.return_response:
            return None
        return {
            "grades": [manager.describe(g) for g in manager.grades],
            "changed": manager.last_changed,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _refresh,
        schema=REFRESH_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = VeracrossManager(
        hass=hass,
        entry_id=entry.entry_id,
        school=entry.data[CONF_SCHOOL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    await manager.async_load()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_MANAGER: manager}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # kick off one fetch at startup so entities are fresh without anyone
    # pressing the button
    async def _initial_fetch() -> None:
        try:
            await manager.async_fetch_grades()
        except Exception:  # noqa: BLE001 - logged/evented inside manager
            pass

    entry.async_create_background_task(hass, _initial_fetch(), "veracross_initial_fetch")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager = VeracrossManager(
        hass=hass,
        entry_id=entry.entry_id,
        school="",
        username="",
        password="",
    )
    await manager.async_load()
    await manager.async_remove_store()
