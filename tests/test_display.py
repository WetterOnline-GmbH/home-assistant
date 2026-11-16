import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientResponseError, ClientSession, web
from custom_components.wohome.number import WoHomeBrightness, async_setup_entry as setup_numbers
from custom_components.wohome.switch import WoHomeAutoBrightnessSwitch, async_setup_entry as setup_switches
from custom_components.wohome.api import WoHomeApi


def test_display_entities():
    coordinator = Mock()
    coordinator.data = {
        "display": {"brightness": 180},
    }
    coordinator.api.set_brightness = AsyncMock()
    coordinator.api.set_auto_brightness = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    number = WoHomeBrightness("test", coordinator)
    assert number.native_value == 71
    assert number.native_min_value == 0
    assert number.native_max_value == 100
    coordinator.data["display"]["brightness"] = 1
    assert number.native_value == 0
    asyncio.run(number.async_set_native_value(0))
    coordinator.api.set_brightness.assert_awaited_with(1)
    asyncio.run(number.async_set_native_value(100))
    coordinator.api.set_brightness.assert_awaited_with(255)
    asyncio.run(number.async_set_native_value(20))
    coordinator.api.set_brightness.assert_awaited_with(51)
    auto_brightness = WoHomeAutoBrightnessSwitch("test", coordinator)
    assert auto_brightness.is_on is None
    coordinator.data["display"]["auto_brightness"] = True
    assert auto_brightness.is_on is True
    asyncio.run(auto_brightness.async_turn_off())
    coordinator.api.set_auto_brightness.assert_awaited_with(False)
    asyncio.run(auto_brightness.async_turn_on())
    coordinator.api.set_auto_brightness.assert_awaited_with(True)

    coordinator.data["display"]["brightness"] = True
    assert number.native_value is None


def test_auto_brightness_capability():
    entry = Mock(unique_id="test")
    coordinator = entry.runtime_data.coordinator
    coordinator.info = {}
    add = Mock()
    asyncio.run(setup_numbers(Mock(), entry, add))
    add.assert_not_called()
    asyncio.run(setup_switches(Mock(), entry, add))
    assert not any(isinstance(entity, WoHomeAutoBrightnessSwitch) for entity in add.call_args.args[0])
    coordinator.info["brightness_control"] = True
    add.reset_mock()
    asyncio.run(setup_numbers(Mock(), entry, add))
    assert isinstance(add.call_args.args[0][0], WoHomeBrightness)
    asyncio.run(setup_switches(Mock(), entry, add))
    assert any(isinstance(entity, WoHomeAutoBrightnessSwitch) for entity in add.call_args.args[0])


def test_api_display_commands():
    async def exercise():
        bodies = []

        async def handler(request):
            bodies.append((request.path, await request.json()))
            if bodies[-1] == ("/api/v1/brightness", {"brightness": 0}):
                return web.json_response({"error": "invalid_request"}, status=400)
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
                await api.set_auto_brightness(True)
                with pytest.raises(ClientResponseError) as error:
                    await api.set_brightness(0)
                assert error.value.status == 400
            assert bodies == [
                ("/api/v1/display", {"is_on": True}),
                ("/api/v1/brightness", {"brightness": 51}),
                ("/api/v1/auto_brightness", {"enabled": True}),
                ("/api/v1/brightness", {"brightness": 0}),
            ]
        finally:
            await runner.cleanup()

    asyncio.run(exercise())
