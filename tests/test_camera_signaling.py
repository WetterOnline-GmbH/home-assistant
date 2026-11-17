import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientSession, web
from homeassistant.components.camera import WebRTCAnswer
from homeassistant.components.http import KEY_HASS_USER

from custom_components.wohome import camera as bridge


@pytest.mark.parametrize("allowed,provider_failure", [(True, False), (False, False), (True, True)])
def test_signaling_and_lazy_hls(monkeypatch, allowed, provider_failure):
    async def exercise():
        camera = Mock()
        camera.async_get_webrtc_client_configuration.return_value.to_frontend_dict.return_value = {
            "configuration": {"iceServers": []}
        }

        async def offer(sdp, session_id, send):
            assert sdp == "example offer"
            if provider_failure:
                raise RuntimeError("provider-specific private details")
            send(WebRTCAnswer("example answer"))

        camera.async_handle_async_webrtc_offer = AsyncMock(side_effect=offer)
        camera.async_on_webrtc_candidate = AsyncMock()
        monkeypatch.setattr(bridge, "get_camera_from_entity_id", lambda *_: camera)
        resolve = AsyncMock(return_value="/hls/example.m3u8")
        monkeypatch.setattr(bridge, "async_request_stream", resolve)
        monkeypatch.setattr(bridge, "dashboard_url", lambda _, path: "http://ha.example" + path)
        user = Mock()
        user.permissions.check_entity.return_value = allowed
        view = bridge.WoHomeCameraView(Mock())

        async def handler(request):
            request[KEY_HASS_USER] = user
            return await view.get(request, "camera.door")

        app = web.Application()
        app.router.add_get("/camera", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                if not allowed:
                    async with session.get(f"http://127.0.0.1:{port}/camera") as response:
                        assert response.status == 403
                    resolve.assert_not_awaited()
                    return
                async with session.ws_connect(f"http://127.0.0.1:{port}/camera") as ws:
                    assert (await ws.receive_json())["type"] == "config"
                    await ws.send_json({"type": "offer", "offer": "example offer"})
                    result = await ws.receive_json()
                    assert result == ({"type": "error"} if provider_failure else {"type": "answer", "answer": "example answer"})
                    resolve.assert_not_awaited()
                async with session.get(f"http://127.0.0.1:{port}/camera") as response:
                    assert response.status == 200
                    assert await response.json() == {"url": "http://ha.example/hls/example.m3u8"}
                resolve.assert_awaited_once()
        finally:
            await runner.cleanup()
        camera.close_webrtc_session.assert_called_once()

    asyncio.run(exercise())
