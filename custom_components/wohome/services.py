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
from homeassistant.helpers import entity_registry as er, target

from .const import DOMAIN
from .dashboard import dashboard_url
from .camera import CAMERA_WEBRTC_PATH, WoHomeCameraView

SERVICE_OPEN_CAMERA = "open_camera"
SERVICE_OPEN_CAMERA_ON_TARGET = "open_camera_on_target"
OPEN_CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("camera_entity_id"): cv.entity_id,
        vol.Optional("duration", default=30): vol.All(cv.positive_int, vol.Range(min=1, max=300)),
    }
)
OPEN_CAMERA_TARGET_SCHEMA = cv.make_entity_service_schema(
    {
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
                runtime = entries[0].runtime_data
                stream_types = get_camera_from_entity_id(hass, entity_id).camera_capabilities.frontend_stream_types
                duration = call.data["duration"]
                if runtime.coordinator.info.get("camera_webrtc") and "web_rtc" in stream_types:
                    path = async_sign_path(
                        hass, CAMERA_WEBRTC_PATH.format(entity_id=entity_id),
                        timedelta(seconds=duration + 20), use_content_user=True,
                    )
                    await runtime.api.open_camera(
                        "", title, duration, webrtc_url=dashboard_url(hass, path)
                    )
                elif not stream_types and runtime.coordinator.info.get("camera_mjpeg"):
                    path = async_sign_path(
                        hass, f"/api/camera_proxy_stream/{entity_id}?interval=1",
                        timedelta(seconds=duration + 20), use_content_user=True,
                    )
                    await runtime.api.open_camera(
                        "", title, duration, mjpeg_url=dashboard_url(hass, path)
                    )
                else:
                    stream_path = await async_request_stream(hass, entity_id, "hls")
                    await runtime.api.open_camera(
                        dashboard_url(hass, stream_path), title, duration
                    )
        except (HomeAssistantError, ClientError, OSError, TimeoutError):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="camera_failed"
            ) from None

    hass.services.async_register(
        DOMAIN, SERVICE_OPEN_CAMERA, open_camera, schema=OPEN_CAMERA_SCHEMA
    )

    async def open_camera_on_target(call: ServiceCall) -> None:
        selection = target.TargetSelection(call.data)
        target_all = call.data.get("entity_id") == "all"
        if target_all:
            entity_ids = set(hass.states.async_entity_ids("switch"))
            if call.data.get("exclude"):
                entity_ids -= target.async_extract_excluded_entity_ids(hass, selection)
        else:
            selected = target.async_extract_referenced_entity_ids(hass, selection)
            entity_ids = selected.referenced | selected.indirectly_referenced

        registry = er.async_get(hass)
        displays = {}
        for entity_id in entity_ids:
            entity = registry.async_get(entity_id)
            if entity is None or entity.platform != DOMAIN or entity.device_id is None:
                continue
            entry = hass.config_entries.async_get_entry(entity.config_entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue
            if entity.entity_id == registry.async_get_entity_id(
                "switch", DOMAIN, f"{entry.unique_id or entry.entry_id}_display"
            ):
                displays[entity.device_id] = entity.entity_id

        if not displays:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_station_unavailable")
        if user_id := call.context.user_id:
            user = await hass.auth.async_get_user(user_id)
            if user is None or not user.permissions.check_entity(call.data["camera_entity_id"], POLICY_READ):
                raise Unauthorized(entity_id=call.data["camera_entity_id"])
            if not user.is_admin:
                allowed = {device_id: entity_id for device_id, entity_id in displays.items()
                           if user.permissions.check_entity(entity_id, POLICY_CONTROL)}
                if not target_all and len(allowed) != len(displays):
                    raise Unauthorized()
                displays = allowed
                if not displays:
                    raise Unauthorized()
        for device_id in sorted(displays):
            await hass.services.async_call(
                DOMAIN, SERVICE_OPEN_CAMERA,
                {"device_id": device_id, "camera_entity_id": call.data["camera_entity_id"],
                 "duration": call.data["duration"]},
                blocking=True, context=call.context,
            )

    hass.services.async_register(
        DOMAIN, SERVICE_OPEN_CAMERA_ON_TARGET, open_camera_on_target, schema=OPEN_CAMERA_TARGET_SCHEMA
    )
