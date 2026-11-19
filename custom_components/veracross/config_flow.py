"""Config flow for Veracross Grades."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SCHOOL, DOMAIN
from .manager import VeracrossError, VeracrossManager

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class VeracrossConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Veracross Grades."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{user_input[CONF_SCHOOL]}_{user_input[CONF_USERNAME]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            manager = VeracrossManager(
                hass=self.hass,
                entry_id="config_flow_validation",
                school=user_input[CONF_SCHOOL],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )

            try:
                await manager.async_fetch_grades()
            except VeracrossError as err:
                _LOGGER.warning("Veracross login validation failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Veracross login")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Veracross ({user_input[CONF_SCHOOL]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
