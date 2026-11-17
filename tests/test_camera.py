import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
import voluptuous as vol
from custom_components.wohome import services
from custom_components.wohome import async_setup


def camera_action(monkeypatch):
    hass = Mock()
    hass.services.has_service.return_value = False
    entry = Mock(domain="wohome", state=ConfigEntryState.LOADED)
    entry.unique_id = "station"
    entry.runtime_data.api.open_camera = AsyncMock()
    entry.runtime_data.coordinator.info = {"camera_control": True}
    hass.config_entries.async_get_entry.return_value = entry
    hass.states.get.return_value = SimpleNamespace(attributes={"friendly_name": "Door"})
    registry = Mock()
    registry.async_get.return_value = SimpleNamespace(config_entry_id="station-entry")
    monkeypatch.setattr(services.dr, "async_get", lambda _: registry)
    entities = Mock()
    entities.async_get_entity_id.return_value = "switch.station_display"
    monkeypatch.setattr(services.er, "async_get", lambda _: entities)
    resolve = AsyncMock(return_value="/api/hls/temporary/master.m3u8")
    monkeypatch.setattr(services, "async_request_stream", resolve)
    camera = SimpleNamespace(camera_capabilities=SimpleNamespace(frontend_stream_types={"hls"}))
    monkeypatch.setattr(services, "get_camera_from_entity_id", lambda *_: camera)
    monkeypatch.setattr(services, "dashboard_url", lambda _, path: "http://ha.example" + path)
    services.async_setup_services(hass)
    handler = hass.services.async_register.call_args.args[2]
    call = SimpleNamespace(context=SimpleNamespace(user_id=None), data=services.OPEN_CAMERA_SCHEMA({
        "device_id": "station", "camera_entity_id": "camera.door",
    }))
    return hass, entry, registry, resolve, handler, call


def test_open_camera_resolves_entity_and_sends_temporary_url(monkeypatch):
    hass, entry, _, resolve, handler, call = camera_action(monkeypatch)
    asyncio.run(handler(call))
    resolve.assert_awaited_once_with(hass, "camera.door", "hls")
    entry.runtime_data.api.open_camera.assert_awaited_once_with(
        "http://ha.example/api/hls/temporary/master.m3u8", "Door", 30
    )


def test_unknown_station_cannot_receive_camera(monkeypatch):
    _, entry, registry, resolve, handler, call = camera_action(monkeypatch)
    registry.async_get.return_value = None
    with pytest.raises(ServiceValidationError):
        asyncio.run(handler(call))
    resolve.assert_not_awaited()
    entry.runtime_data.api.open_camera.assert_not_awaited()


@pytest.mark.parametrize("stream_types", [{"web_rtc"}, {"hls", "web_rtc"}])
def test_webrtc_is_preferred_without_starting_hls(monkeypatch, stream_types):
    hass, entry, _, resolve, handler, call = camera_action(monkeypatch)
    entry.runtime_data.coordinator.info["camera_webrtc"] = True
    camera = SimpleNamespace(camera_capabilities=SimpleNamespace(frontend_stream_types=stream_types))
    monkeypatch.setattr(services, "get_camera_from_entity_id", lambda *_: camera)
    monkeypatch.setattr(services, "async_sign_path", lambda *a, **k: "/api/wohome/camera/camera.door/webrtc?authSig=example")
    asyncio.run(handler(call))
    resolve.assert_not_awaited()
    entry.runtime_data.api.open_camera.assert_awaited_once_with(
        "", "Door", 30, webrtc_url="http://ha.example/api/wohome/camera/camera.door/webrtc?authSig=example"
    )


def test_legacy_device_registry_is_supported(monkeypatch):
    _, entry, registry, _, handler, call = camera_action(monkeypatch)
    registry.async_get.return_value = SimpleNamespace(config_entries={"station-entry"})
    asyncio.run(handler(call))
    entry.runtime_data.api.open_camera.assert_awaited_once()


def test_camera_read_permission_is_required(monkeypatch):
    hass, entry, _, resolve, handler, call = camera_action(monkeypatch)
    call.context.user_id = "viewer"
    user = Mock()
    user.permissions.check_entity.return_value = False
    hass.auth.async_get_user = AsyncMock(return_value=user)
    with pytest.raises(Unauthorized):
        asyncio.run(handler(call))
    resolve.assert_not_awaited()
    entry.runtime_data.api.open_camera.assert_not_awaited()


@pytest.mark.parametrize("can_control", [True, False])
def test_station_control_permission_is_required(monkeypatch, can_control):
    hass, entry, _, resolve, handler, call = camera_action(monkeypatch)
    call.context.user_id = "viewer"
    user = Mock(is_admin=False)
    user.permissions.check_entity.side_effect = lambda entity_id, _: entity_id == "camera.door" or can_control
    hass.auth.async_get_user = AsyncMock(return_value=user)
    if can_control:
        asyncio.run(handler(call))
        entry.runtime_data.api.open_camera.assert_awaited_once()
    else:
        with pytest.raises(Unauthorized):
            asyncio.run(handler(call))
        resolve.assert_not_awaited()
        entry.runtime_data.api.open_camera.assert_not_awaited()


def test_stream_failure_does_not_expose_sensitive_url(monkeypatch):
    _, entry, _, resolve, handler, call = camera_action(monkeypatch)
    resolve.side_effect = HomeAssistantError("rtsp://user:secret@camera.example/stream")
    with pytest.raises(HomeAssistantError) as error:
        asyncio.run(handler(call))
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__
    entry.runtime_data.api.open_camera.assert_not_awaited()


@pytest.mark.parametrize("duration", [0, -1, 301])
def test_duration_is_bounded(duration):
    with pytest.raises(vol.Invalid):
        services.OPEN_CAMERA_SCHEMA({
            "device_id": "station", "camera_entity_id": "camera.door", "duration": duration,
        })


def test_service_is_registered_once():
    hass = Mock()
    hass.services.has_service.return_value = True
    services.async_setup_services(hass)
    hass.services.async_register.assert_not_called()


def test_camera_service_is_available_before_a_station_connects():
    hass = Mock()
    hass.services.has_service.return_value = False
    assert asyncio.run(async_setup(hass, {}))
    hass.http.register_view.assert_called_once()
    hass.services.async_register.assert_called_once()
    hass.config_entries.async_get_entry.assert_not_called()
