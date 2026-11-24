from __future__ import annotations

import asyncio
from datetime import timedelta

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.components.camera import async_request_stream, get_camera_from_entity_id
from homeassistant.components.http.auth import async_sign_path
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .dashboard import dashboard_url
from .camera import CAMERA_WEBRTC_PATH, WoHomeCameraView

SERVICE_OPEN_CAMERA = "open_camera"
OPEN_CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("camera_entity_id"): cv.entity_id,
        vol.Optional("duration", default=30): vol.All(cv.positive_int, vol.Range(min=1, max=300)),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_OPEN_CAMERA):
        return
    hass.http.register_view(WoHomeCameraView(hass))

    async def open_camera(call: ServiceCall) -> None:
        device = dr.async_get(hass).async_get(call.data["device_id"])
        entry_ids = () if device is None else (
            (device.config_entry_id,) if hasattr(device, "config_entry_id") else device.config_entries
        )
        entries = [
            entry for entry_id in entry_ids
            if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
            and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED
        ]
        if len(entries) != 1:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_station_unavailable")
        if not entries[0].runtime_data.coordinator.info.get("camera_control"):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_unsupported")
        entity_id = call.data["camera_entity_id"]
        if user_id := call.context.user_id:
            user = await hass.auth.async_get_user(user_id)
            if user is None or not user.permissions.check_entity(entity_id, POLICY_READ):
                raise Unauthorized(entity_id=entity_id)
            if not user.is_admin:
                entry = entries[0]
                display_id = er.async_get(hass).async_get_entity_id(
                    "switch", DOMAIN, f"{entry.unique_id or entry.entry_id}_display"
                )
                if display_id is None or not user.permissions.check_entity(display_id, POLICY_CONTROL):
                    raise Unauthorized()
        camera = hass.states.get(entity_id)
        if not entity_id.startswith("camera.") or camera is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_not_found")
        title = str(camera.attributes.get("friendly_name") or entity_id).strip()[:120] or entity_id
        try:
            async with asyncio.timeout(30):
                supports_webrtc = "web_rtc" in get_camera_from_entity_id(hass, entity_id).camera_capabilities.frontend_stream_types
                if entries[0].runtime_data.coordinator.info.get("camera_webrtc") and supports_webrtc:
                    path = async_sign_path(
                        hass, CAMERA_WEBRTC_PATH.format(entity_id=entity_id),
                        timedelta(seconds=call.data["duration"] + 20), use_content_user=True,
                    )
                    await entries[0].runtime_data.api.open_camera(
                        "", title, call.data["duration"], webrtc_url=dashboard_url(hass, path)
                    )
                else:
                    stream_path = await async_request_stream(hass, entity_id, "hls")
                    await entries[0].runtime_data.api.open_camera(
                        dashboard_url(hass, stream_path), title, call.data["duration"]
                    )
        except (HomeAssistantError, ClientError, OSError, TimeoutError):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="camera_failed"
            ) from None

    hass.services.async_register(
        DOMAIN, SERVICE_OPEN_CAMERA, open_camera, schema=OPEN_CAMERA_SCHEMA
    )
