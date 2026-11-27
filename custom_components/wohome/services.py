from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from uuid import uuid4

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.components.camera import async_request_stream, get_camera_from_entity_id
from homeassistant.components.http.auth import async_sign_path
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import entity_registry as er, target

from .api import WoHomeApi
from .const import DOMAIN
from .dashboard import dashboard_url
from .camera import CAMERA_WEBRTC_PATH, WoHomeCameraView

SERVICE_OPEN_CAMERA = "open_camera"
SERVICE_OPEN_CAMERA_ON_TARGET = "open_camera_on_target"
LOGGER = logging.getLogger(__name__)
CAMERA_FIELDS = {
    vol.Required("camera_entity_id"): cv.entity_id,
    vol.Optional("duration", default=30): vol.All(cv.positive_int, vol.Range(min=1, max=300)),
    vol.Optional("action_script"): cv.entity_domain("script"),
    vol.Optional("action_label"): vol.All(cv.string, str.strip, vol.Length(min=1, max=40)),
}
OPEN_CAMERA_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string, **CAMERA_FIELDS})
OPEN_CAMERA_TARGET_SCHEMA = cv.make_entity_service_schema(CAMERA_FIELDS)


async def _async_check_camera_script(hass: HomeAssistant, script: str, context: Context) -> None:
    if user_id := context.user_id:
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_active or not user.permissions.check_entity(script, POLICY_CONTROL):
            raise Unauthorized(entity_id=script)
    state = hass.states.get(script)
    if state is None or state.state == STATE_UNAVAILABLE:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_script_unavailable")


async def _async_handle_camera_action(
    hass: HomeAssistant, api: WoHomeApi, action_id: str, script: str, deadline: float, context: Context,
) -> None:
    pressed = False
    accepted = False
    try:
        async with asyncio.timeout_at(deadline):
            while (status := await api.poll_camera_action(action_id)) == "waiting":
                await asyncio.sleep(0.1)
            if status != "pressed":
                return
            pressed = True
            await _async_check_camera_script(hass, script, context)
            if asyncio.get_running_loop().time() >= deadline:
                return
            await hass.services.async_call(
                "script", "turn_on", {ATTR_ENTITY_ID: script}, blocking=True, context=context,
            )
            accepted = True
    except TimeoutError:
        pass
    except (HomeAssistantError, ClientError, OSError, ValueError, KeyError):
        LOGGER.debug("Could not process the wetteronline home camera button press")
    if pressed:
        try:
            await api.finish_camera_action(action_id, accepted)
        except (ClientError, OSError, TimeoutError, ValueError):
            LOGGER.debug("Could not send camera button feedback to wetteronline home")


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
        script = call.data.get("action_script")
        action_label = call.data.get("action_label")
        if (script is None) != (action_label is None):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="camera_action_incomplete")
        entry = entries[0]
        runtime = entry.runtime_data
        action_id = None
        camera_options = {}
        if script is not None and runtime.coordinator.info.get("camera_action") is True:
            await _async_check_camera_script(hass, script, call.context)
            action_id = uuid4().hex
            camera_options["action"] = {"id": action_id, "label": action_label}
        title = str(camera.attributes.get("friendly_name") or entity_id).strip()[:120] or entity_id
        duration = call.data["duration"]
        try:
            async with asyncio.timeout(30):
                stream_types = get_camera_from_entity_id(hass, entity_id).camera_capabilities.frontend_stream_types
                url = ""
                if runtime.coordinator.info.get("camera_webrtc") and "web_rtc" in stream_types:
                    path = async_sign_path(
                        hass, CAMERA_WEBRTC_PATH.format(entity_id=entity_id),
                        timedelta(seconds=duration + 20), use_content_user=True,
                    )
                    camera_options["webrtc_url"] = dashboard_url(hass, path)
                elif not stream_types and runtime.coordinator.info.get("camera_mjpeg"):
                    # interval selects Home Assistant's still-image stream at one frame per second; without it the camera's own stream handler is used.
                    path = async_sign_path(
                        hass, f"/api/camera_proxy_stream/{entity_id}?interval=1",
                        timedelta(seconds=duration + 20), use_content_user=True,
                    )
                    camera_options["mjpeg_url"] = dashboard_url(hass, path)
                else:
                    stream_path = await async_request_stream(hass, entity_id, "hls")
                    url = dashboard_url(hass, stream_path)
                deadline = asyncio.get_running_loop().time() + duration
                await runtime.api.open_camera(url, title, duration, **camera_options)
        except (HomeAssistantError, ClientError, OSError, TimeoutError):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="camera_failed"
            ) from None
        if action_id is not None:
            entry.async_create_background_task(
                hass, _async_handle_camera_action(hass, runtime.api, action_id, script, deadline, call.context),
                "wohome camera action",
            )

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
        camera_data = {key: call.data[key] for key in (
            "camera_entity_id", "duration", "action_script", "action_label",
        ) if key in call.data}
        for device_id in sorted(displays):
            await hass.services.async_call(
                DOMAIN, SERVICE_OPEN_CAMERA,
                {"device_id": device_id, **camera_data},
                blocking=True, context=call.context,
            )

    hass.services.async_register(
        DOMAIN, SERVICE_OPEN_CAMERA_ON_TARGET, open_camera_on_target, schema=OPEN_CAMERA_TARGET_SCHEMA
    )
