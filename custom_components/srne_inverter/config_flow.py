"""Konfiguracja przez UI."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import SrneClient, SrneError
from .const import (
    CONF_LOCK_MINUTES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_LOCK_MINUTES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)

INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=2, max=300))
PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _valid_password(value: str) -> bool:
    return value == "" or (value.isdigit() and int(value) <= 65535)


class SrneConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SrneOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_PASSWORD] = str(user_input.get(CONF_PASSWORD, "")).strip()
            if not _valid_password(user_input[CONF_PASSWORD]):
                errors[CONF_PASSWORD] = "invalid_password"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_SLAVE]}"
                )
                self._abort_if_unique_id_configured()
                client = SrneClient(
                    user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE]
                )
                try:
                    await client.connect()
                    await client.read(256, 1)  # SOC baterii
                except SrneError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
                finally:
                    await client.close()

        d = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=d.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_SLAVE, default=d.get(CONF_SLAVE, DEFAULT_SLAVE)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): INTERVAL,
                vol.Optional(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): PASSWORD,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class SrneOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        entry = self.config_entry
        if user_input is not None:
            user_input[CONF_PASSWORD] = str(user_input.get(CONF_PASSWORD, "")).strip()
            if _valid_password(user_input[CONF_PASSWORD]):
                return self.async_create_entry(data=user_input)
            errors[CONF_PASSWORD] = "invalid_password"

        interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        password = entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD, ""))
        lock_minutes = entry.options.get(CONF_LOCK_MINUTES, DEFAULT_LOCK_MINUTES)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=interval): INTERVAL,
                    vol.Optional(CONF_PASSWORD, default=password): PASSWORD,
                    vol.Optional(CONF_LOCK_MINUTES, default=lock_minutes): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=1440)
                    ),
                }
            ),
            errors=errors,
        )
