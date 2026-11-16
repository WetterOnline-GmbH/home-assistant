import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from unittest.mock import patch

import pytest
from aiohttp import ClientResponseError, ClientSession, web
from homeassistant.exceptions import ServiceValidationError
from homeassistant.const import EntityCategory
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA, PLATFORM_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.helpers.service import _SERVICES_SCHEMA
from homeassistant.util.yaml import load_yaml_dict

from custom_components.wohome.binary_sensor import WoHomeScheduledOn
from custom_components.wohome.button import WoHomeRestoreBrightness
from custom_components.wohome.button import async_setup_entry as setup_buttons
from custom_components.wohome.number import WoHomeBrightness
from custom_components.wohome.sensor import WoHomeDisplayRules
from custom_components.wohome.services import async_setup_services
from custom_components.wohome.switch import WoHomeAutoBrightnessSwitch, async_setup_entry as setup_switches
from custom_components.wohome.api import WoHomeApi


def test_display_entities():
    coordinator = Mock()
    coordinator.data = {
        "display": {"brightness": 180, "brightness_override": None},
        "scheduled_on": True,
        "display_rules": [{"is_active": True}],
    }
    coordinator.api.set_brightness = AsyncMock()
    coordinator.api.set_auto_brightness = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    number = WoHomeBrightness("test", coordinator)
    assert number.native_value == 71
    coordinator.data["display"]["brightness_override"] = 51
    assert number.native_value == 20
    assert WoHomeScheduledOn("test", coordinator).is_on is True
    rules = WoHomeDisplayRules("test", coordinator)
    assert rules.entity_category == EntityCategory.DIAGNOSTIC
    assert rules.native_value == 1
    assert rules.extra_state_attributes["rules"] == coordinator.data["display_rules"]

    asyncio.run(number.async_set_native_value(20))
    coordinator.api.set_brightness.assert_awaited_with(51)
    asyncio.run(WoHomeRestoreBrightness("test", coordinator).async_press())
    coordinator.api.set_brightness.assert_awaited_with(None)
    auto_brightness = WoHomeAutoBrightnessSwitch("test", coordinator)
    assert auto_brightness.is_on is None
    coordinator.data["display"]["auto_brightness"] = True
    assert auto_brightness.is_on is True
    asyncio.run(auto_brightness.async_turn_off())
    coordinator.api.set_auto_brightness.assert_awaited_with(False)
    asyncio.run(auto_brightness.async_turn_on())
    coordinator.api.set_auto_brightness.assert_awaited_with(True)

    coordinator.data["scheduled_on"] = None
    coordinator.data["display"]["brightness_override"] = None
    coordinator.data["display"]["brightness"] = True
    assert WoHomeScheduledOn("test", coordinator).is_on is None
    assert number.native_value is None


def test_auto_brightness_capability_and_legacy_button():
    entry = Mock(unique_id="test")
    coordinator = entry.runtime_data.coordinator
    coordinator.info = {"brightness_control": True}
    add = Mock()
    asyncio.run(setup_buttons(Mock(), entry, add))
    assert isinstance(add.call_args.args[0][0], WoHomeRestoreBrightness)
    coordinator.info["auto_brightness_control"] = True
    add.reset_mock()
    asyncio.run(setup_buttons(Mock(), entry, add))
    add.assert_not_called()
    asyncio.run(setup_switches(Mock(), entry, add))
    assert any(isinstance(entity, WoHomeAutoBrightnessSwitch) for entity in add.call_args.args[0])


def test_update_rules_service():
    hass = Mock()
    entry = Mock()
    coordinator = entry.runtime_data.coordinator
    coordinator.info = {"display_rules_control": True}
    coordinator.api.set_display_rules = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    with patch("custom_components.wohome.services.service.async_register_admin_service") as register:
        async_setup_services(hass)
        handler = register.call_args.args[3]
    call = Mock(data={"config_entry_id": "entry", "expected": [], "rules": []})
    with patch("custom_components.wohome.services.service.async_get_config_entry", return_value=entry):
        asyncio.run(handler(call))
        coordinator.api.set_display_rules.assert_awaited_once_with([], [])
        coordinator.info = {}
        with pytest.raises(ServiceValidationError):
            asyncio.run(handler(call))


def test_blueprint_and_service_schemas():
    root = Path(__file__).resolve().parents[1]
    blueprint = Blueprint(
        load_yaml_dict(root / "blueprints/automation/wohome/presence_display.yaml"),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    inputs = BlueprintInputs(blueprint, {"use_blueprint": {"input": {
        "presence": "binary_sensor.presence",
        "display": "switch.screen",
        "brightness": "number.screen_brightness",
        "schedule": "binary_sensor.screen_schedule",
    }}})
    inputs.validate()
    hass = Mock()
    hass.data = {}
    with patch("homeassistant.helpers.config_validation._async_get_hass_or_none", return_value=hass):
        PLATFORM_SCHEMA(inputs.async_substitute())
    _SERVICES_SCHEMA(load_yaml_dict(root / "custom_components/wohome/services.yaml"))


def test_api_display_commands():
    async def exercise():
        bodies = []

        async def handler(request):
            bodies.append((request.path, await request.json()))
            if request.path.endswith("display_rules"):
                return web.json_response({"error": "display_rules_changed"}, status=409)
            return web.json_response({})

        app = web.Application()
        app.router.add_put("/api/v1/{path}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                api = WoHomeApi(session, "127.0.0.1", port)
                await api.set_display(True)
                await api.set_brightness(51)
                await api.set_brightness(None)
                await api.set_auto_brightness(True)
                with pytest.raises(ClientResponseError) as error:
                    await api.set_display_rules([], [])
                assert error.value.status == 409
            assert bodies == [
                ("/api/v1/display", {"is_on": True, "respect_schedule": True}),
                ("/api/v1/brightness", {"brightness": 51}),
                ("/api/v1/brightness", {"brightness": None}),
                ("/api/v1/auto_brightness", {"enabled": True}),
                ("/api/v1/display_rules", {"expected": [], "rules": []}),
            ]
        finally:
            await runner.cleanup()

    asyncio.run(exercise())
