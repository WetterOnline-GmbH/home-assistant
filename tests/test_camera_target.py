import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
try:
    from probatio import Invalid as SchemaInvalid
except ImportError:
    from voluptuous import Invalid as SchemaInvalid
from homeassistant.components.websocket_api.automation import async_get_services_for_target
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers import floor_registry as fr, label_registry as lr
from homeassistant.helpers import service
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import entity_sources
from homeassistant.util.yaml import load_yaml_dict

from custom_components.wohome import services

pytestmark = pytest.mark.skipif(
    not hasattr(cv, "TARGET_EXCLUDE_SCHEMA"), reason="Home Assistant does not support target exclusions"
)


def test_camera_target_discovery_and_execution(tmp_path, monkeypatch):
    asyncio.run(exercise_camera_target(tmp_path, monkeypatch))


async def exercise_camera_target(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = Mock()
    hass.config_entries.async_wait_initialized = AsyncMock()
    hass.http = Mock()
    hass.auth = Mock()
    dr.async_setup(hass)
    await ar.async_load(hass, load_empty=True)
    await dr.async_load(hass, load_empty=True)
    await er.async_load(hass, load_empty=True)
    await fr.async_load(hass, load_empty=True)
    await lr.async_load(hass, load_empty=True)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    area = ar.async_get(hass).async_create("Room")
    floor = fr.async_get(hass).async_create("Floor")
    label = lr.async_get(hass).async_create("Stations")
    ar.async_get(hass).async_update(area.id, floor_id=floor.floor_id, labels={label.label_id})
    entries = {}
    hass.config_entries.async_get_entry.side_effect = entries.get
    stations = []
    for name in ("one", "two"):
        entry = Mock(domain="wohome", state=ConfigEntryState.LOADED, entry_id=name, unique_id=name)
        entry.pref_disable_new_entities = False
        entry.disabled_by = None
        entry.runtime_data.coordinator.info = {"camera_control": True}
        entry.runtime_data.api.open_camera = AsyncMock()
        entries[name] = entry
        device = devices.async_get_or_create(config_entry_id=name, identifiers={("wohome", name)})
        devices.async_update_device(device.id, area_id=area.id)
        display = entities.async_get_or_create(
            "switch", "wohome", f"{name}_display", config_entry=entry, device_id=device.id,
            suggested_object_id=f"{name}_display",
        )
        hass.states.async_set(display.entity_id, "on")
        entity_sources(hass)[display.entity_id] = {"domain": "wohome"}
        stations.append((entry, device, display))
    hass.states.async_set("camera.example", "idle", {"friendly_name": "Camera"})
    other = entities.async_get_or_create("switch", "other", "other", suggested_object_id="other")
    hass.states.async_set(other.entity_id, "on")
    entity_sources(hass)[other.entity_id] = {"domain": "other"}
    monkeypatch.setattr(services, "get_camera_from_entity_id", lambda *_: SimpleNamespace(
        camera_capabilities=SimpleNamespace(frontend_stream_types={"hls"})
    ))
    monkeypatch.setattr(services, "async_request_stream", AsyncMock(return_value="/stream"))
    monkeypatch.setattr(services, "dashboard_url", lambda _, path: "http://example.test" + path)
    services.async_setup_services(hass)
    descriptions = load_yaml_dict(str(Path(__file__).resolve().parents[1] / "custom_components/wohome/services.yaml"))
    for name in ("open_camera", "open_camera_on_target"):
        service.async_set_service_schema(hass, "wohome", name, descriptions[name])

    first, second = stations
    available = await async_get_services_for_target(hass, {"device_id": first[1].id}, True)
    assert "wohome.open_camera_on_target" in available
    assert "wohome.open_camera" not in available
    assert "wohome.open_camera_on_target" not in await async_get_services_for_target(
        hass, {"entity_id": other.entity_id}, True
    )

    async def call(target_data, **kwargs):
        await hass.services.async_call(
            "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example", **kwargs},
            target=target_data, blocking=True,
        )

    await call({"device_id": first[1].id, "entity_id": first[2].entity_id}, duration=42)
    first[0].runtime_data.api.open_camera.assert_awaited_once_with("http://example.test/stream", "Camera", 42)
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    first[0].runtime_data.api.open_camera.reset_mock()
    await call({"area_id": area.id, "exclude": {"entity_id": first[2].entity_id}})
    first[0].runtime_data.api.open_camera.assert_not_awaited()
    second[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.reset_mock()
    params = service.async_prepare_call_from_config(hass, {
        "action": "wohome.open_camera_on_target",
        "target": {"area_id": area.id, "exclude": {"device_id": first[1].id}},
        "data": {"camera_entity_id": "camera.example"},
    }, validate_config=True)
    await hass.services.async_call(**params, blocking=True)
    first[0].runtime_data.api.open_camera.assert_not_awaited()
    second[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.reset_mock()
    for invalid_target in (
        {"exclude": {"device_id": first[1].id}},
        {"area_id": area.id, "exclude": {"unexpected": first[1].id}},
    ):
        with pytest.raises(HomeAssistantError):
            service.async_prepare_call_from_config(hass, {
                "action": "wohome.open_camera_on_target", "target": invalid_target,
                "data": {"camera_entity_id": "camera.example"},
            }, validate_config=True)
    await call({"entity_id": "all", "exclude": {"device_id": second[1].id}})
    first[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    first[0].runtime_data.api.open_camera.reset_mock()
    await call({"floor_id": floor.floor_id, "exclude": {"device_id": second[1].id}})
    first[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    first[0].runtime_data.api.open_camera.reset_mock()
    await call({"label_id": label.label_id})
    first[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.assert_awaited_once()
    first[0].runtime_data.api.open_camera.reset_mock()
    second[0].runtime_data.api.open_camera.reset_mock()
    for duration in (0, -1, 301):
        with pytest.raises((SchemaInvalid, ServiceValidationError)):
            await call({"device_id": first[1].id}, duration=duration)
    with pytest.raises(ServiceValidationError):
        await call({"entity_id": other.entity_id})
    first[0].runtime_data.coordinator.info["camera_control"] = False
    with pytest.raises(ServiceValidationError):
        await call({"device_id": first[1].id})
    first[0].runtime_data.coordinator.info["camera_control"] = True
    user = Mock(is_admin=False)
    user.permissions.check_entity.side_effect = lambda entity_id, _: entity_id == "camera.example"
    hass.auth.async_get_user = AsyncMock(return_value=user)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example"},
            target={"entity_id": "all"}, blocking=True, context=Context(user_id="user"),
        )
    first[0].runtime_data.api.open_camera.assert_not_awaited()
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example"},
            target={"entity_id": first[2].entity_id}, blocking=True, context=Context(user_id="user"),
        )
    first[0].runtime_data.api.open_camera.assert_not_awaited()
    user.permissions.check_entity.side_effect = lambda entity_id, _: entity_id in {
        "camera.example", first[2].entity_id
    }
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example"},
            target={"area_id": area.id}, blocking=True, context=Context(user_id="user"),
        )
    first[0].runtime_data.api.open_camera.assert_not_awaited()
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    await hass.services.async_call(
        "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example"},
        target={"entity_id": "all"}, blocking=True, context=Context(user_id="user"),
    )
    first[0].runtime_data.api.open_camera.assert_awaited_once()
    second[0].runtime_data.api.open_camera.assert_not_awaited()
    first[0].runtime_data.api.open_camera.reset_mock()
    user.permissions.check_entity.return_value = False
    user.permissions.check_entity.side_effect = None
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "wohome", "open_camera_on_target", {"camera_entity_id": "camera.example"},
            target={"entity_id": first[2].entity_id}, blocking=True, context=Context(user_id="user"),
        )
    first[0].runtime_data.api.open_camera.assert_not_awaited()

    await hass.services.async_call(
        "wohome", "open_camera", {"device_id": first[1].id, "camera_entity_id": "camera.example"},
        blocking=True,
    )
    first[0].runtime_data.api.open_camera.assert_awaited_once()
