from __future__ import annotations

from typing import Any
import hashlib
import secrets

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, SOURCE_RECONFIGURE
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import WoHomeApi
from .const import (
    API_VERSION,
    CONF_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)


class WoHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered_values: dict[str, Any] = {}
        self._pairing: tuple[WoHomeApi, str, str, bytes, str] | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        properties = {
            key: value.lower() if isinstance(value, str) else value
            for key, value in discovery_info.properties.items()
        }
        if (
            properties.get("model") != MODEL.lower()
            or properties.get("manufacturer") != MANUFACTURER.lower()
        ):
            return self.async_abort(reason="not_wohome")

        device_id = discovery_info.properties.get("id")
        if not device_id:
            return self.async_abort(reason="no_device_id")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: discovery_info.host,
                CONF_PORT: discovery_info.port,
            }
        )
        self._discovered_values = {
            CONF_HOST: discovery_info.host,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
            CONF_NAME: _device_name(device_id),
        }
        self.context["title_placeholders"] = {
            "name": self._discovered_values[CONF_NAME]
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "name": self._discovered_values[CONF_NAME]
                },
            )

        host = self._discovered_values[CONF_HOST]
        port = self._discovered_values[CONF_PORT]
        try:
            info = await self._device_info(host, port)
        except (ClientError, TimeoutError, KeyError, OSError, ValueError):
            return self.async_abort(reason="cannot_connect")

        if info.get("api_version") != API_VERSION:
            return self.async_abort(reason="unsupported_api")

        device_name = str(info.get("name") or self._discovered_values[CONF_NAME])
        self._discovered_values[CONF_NAME] = device_name
        return await self.async_step_pairing()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        defaults = {
            CONF_HOST: "",
            CONF_PORT: DEFAULT_PORT,
        }

        if user_input is not None:
            try:
                info = await self._device_info(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )
                if info.get("api_version") != API_VERSION:
                    errors["base"] = "unsupported_api"
                else:
                    await self.async_set_unique_id(str(info["id"]))
                    self._abort_if_unique_id_configured()
                    device_name = str(info.get("name") or DEFAULT_NAME)
                    self._discovered_values = {**user_input, CONF_NAME: device_name}
                    return await self.async_step_pairing()
            except (ClientError, TimeoutError, KeyError, OSError, ValueError):
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): cv.port,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._device_info(user_input[CONF_HOST], user_input[CONF_PORT])
                if info.get("api_version") != API_VERSION:
                    errors["base"] = "unsupported_api"
                elif str(info.get("id")) != entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    await self.async_set_unique_id(str(info["id"]))
                    self._abort_if_unique_id_mismatch()
                    self._discovered_values = {
                        **user_input,
                        CONF_NAME: str(info.get("name") or entry.title),
                    }
                    return await self.async_step_pairing()
            except (ClientError, TimeoutError, OSError, ValueError, KeyError):
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
            vol.Required(CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)): cv.port,
        })
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def _device_info(self, host: str, port: int) -> dict[str, Any]:
        api = WoHomeApi(async_get_clientsession(self.hass), host, port)
        return await api.get_info()

    async def async_step_pairing(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._set_confirm_only()
        if self._pairing is None:
            host = self._discovered_values[CONF_HOST]
            port = self._discovered_values[CONF_PORT]
            api = WoHomeApi(async_get_clientsession(self.hass), host, port)
            nonce = secrets.token_urlsafe(32)
            try:
                ticket, certificate = await api.start_pairing(nonce)
            except ClientResponseError as error:
                return self.async_abort(reason="pairing_unavailable" if error.status == 409 else "cannot_connect")
            except (ClientError, TimeoutError, OSError, ValueError, KeyError):
                return self.async_abort(reason="cannot_connect")
            digest = hashlib.sha256(certificate + nonce.encode("ascii") + ticket.encode("ascii")).digest()
            code = "-".join(bytes(digest[:6]).hex().upper()[i:i+4] for i in range(0, 12, 4))
            self._pairing = (api, ticket, nonce, certificate, code)

        api, ticket, _, certificate, code = self._pairing
        if user_input is not None:
            key = secrets.token_urlsafe(32)
            try:
                await api.complete_pairing(ticket, key, certificate)
            except (ClientError, TimeoutError, OSError, ValueError):
                return self.async_show_form(step_id="pairing", errors={"base": "not_confirmed"},
                                            description_placeholders={"code": code})
            data = {**self._discovered_values, "key": key,
                    "fingerprint": hashlib.sha256(certificate).hexdigest()}
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=data,
                )
            return self.async_create_entry(title=self._discovered_values[CONF_NAME], data=data)

        return self.async_show_form(step_id="pairing", description_placeholders={"code": code})


def _device_name(device_id: str) -> str:
    return f"wohome4-{device_id}"
