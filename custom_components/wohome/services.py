from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def set_display_rules(call: ServiceCall) -> None:
        entry = service.async_get_config_entry(hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID])
        coordinator = entry.runtime_data.coordinator
        if coordinator.info.get("display_rules_control") is not True:
            raise ServiceValidationError("The device does not support editing display rules")
        try:
            await coordinator.api.set_display_rules(call.data["expected"], call.data["rules"])
        except (ClientError, TimeoutError, OSError) as error:
            await coordinator.async_request_refresh()
            raise HomeAssistantError(f"Could not update display rules: {error}") from error
        await coordinator.async_request_refresh()

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "set_display_rules",
        set_display_rules,
        schema=vol.Schema({
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required("expected"): [dict],
            vol.Required("rules"): [dict],
        }),
    )
