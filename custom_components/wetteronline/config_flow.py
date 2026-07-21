"""Config flow for the WetterOnline Weather integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    Location,
    WetterOnlineApiClient,
    WetterOnlineAuthError,
    WetterOnlineConnectionError,
)
from .const import (
    CONF_ACCOUNT_TIER,
    CONF_LOCATION_ID,
    CONF_LOCATION_LABEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

CONF_LOCATION_QUERY = "location_query"


async def _resolve_location(
    client: WetterOnlineApiClient, user_input: dict[str, Any]
) -> Location:
    """Resolve a Location from either a free-text query or raw coordinates."""
    query = user_input.get(CONF_LOCATION_QUERY)
    if query:
        results = await client.async_search_location(query)
        return results[0]

    lat = user_input[CONF_LATITUDE]
    lon = user_input[CONF_LONGITUDE]
    return Location(
        id=f"{lat:.4f},{lon:.4f}",
        lat=lat,
        lon=lon,
        label=f"WetterOnline ({lat:.2f}, {lon:.2f})",
    )


class WetterOnlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WetterOnline Weather."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._account_tier: str | None = None
        self._discovered: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = WetterOnlineApiClient(
                async_get_clientsession(self.hass), user_input[CONF_API_KEY]
            )
            try:
                account = await client.async_validate_key()
            except WetterOnlineAuthError:
                errors["base"] = "invalid_auth"
            except (WetterOnlineConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                self._api_key = user_input[CONF_API_KEY]
                self._account_tier = account.get("tier", "basic")
                return await self.async_step_location()

        schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = WetterOnlineApiClient(
                async_get_clientsession(self.hass), self._api_key or ""
            )
            try:
                location = await _resolve_location(client, user_input)
            except (WetterOnlineConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(location.id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=location.label,
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_LOCATION_ID: location.id,
                        CONF_LATITUDE: location.lat,
                        CONF_LONGITUDE: location.lon,
                        CONF_LOCATION_LABEL: location.label,
                        CONF_ACCOUNT_TIER: self._account_tier,
                    },
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_LOCATION_QUERY): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): vol.Coerce(float),
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="location", data_schema=schema, errors=errors
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle discovery handed off by the wohome station integration."""
        location_info = discovery_info["location"]
        location = Location(
            id=location_info["id"],
            lat=location_info["lat"],
            lon=location_info["lon"],
            label=location_info["label"],
        )

        await self.async_set_unique_id(location.id)
        self._abort_if_unique_id_configured()

        self._api_key = discovery_info["api_key"]
        self._account_tier = discovery_info.get("account_tier", "basic")
        self._discovered = {
            CONF_API_KEY: self._api_key,
            CONF_LOCATION_ID: location.id,
            CONF_LATITUDE: location.lat,
            CONF_LONGITUDE: location.lon,
            CONF_LOCATION_LABEL: location.label,
            CONF_ACCOUNT_TIER: self._account_tier,
        }
        self.context["title_placeholders"] = {"name": location.label}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={
                    "name": self._discovered[CONF_LOCATION_LABEL]
                },
            )

        return self.async_create_entry(
            title=self._discovered[CONF_LOCATION_LABEL],
            data=self._discovered,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = WetterOnlineApiClient(
                async_get_clientsession(self.hass), user_input[CONF_API_KEY]
            )
            try:
                await client.async_validate_key()
            except WetterOnlineAuthError:
                errors["base"] = "invalid_auth"
            except (WetterOnlineConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                    reason="reauth_successful",
                )

        schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            client = WetterOnlineApiClient(
                async_get_clientsession(self.hass),
                reconfigure_entry.data[CONF_API_KEY],
            )
            try:
                location = await _resolve_location(client, user_input)
            except (WetterOnlineConnectionError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(location.id)
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=location.label,
                    data_updates={
                        CONF_LOCATION_ID: location.id,
                        CONF_LATITUDE: location.lat,
                        CONF_LONGITUDE: location.lon,
                        CONF_LOCATION_LABEL: location.label,
                    },
                    reason="reconfigure_successful",
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_LOCATION_QUERY): str,
                vol.Required(
                    CONF_LATITUDE, default=reconfigure_entry.data[CONF_LATITUDE]
                ): vol.Coerce(float),
                vol.Required(
                    CONF_LONGITUDE, default=reconfigure_entry.data[CONF_LONGITUDE]
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WetterOnlineOptionsFlow:
        return WetterOnlineOptionsFlow()


class WetterOnlineOptionsFlow(OptionsFlow):
    """Handle WetterOnline Weather options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=60)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
