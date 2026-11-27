import asyncio
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientSession, web

from custom_components.wohome.api import WoHomeApi


def test_camera_api_sends_mjpeg_url(monkeypatch):
    put_json = AsyncMock()
    monkeypatch.setattr(WoHomeApi, "_put_json", put_json)
    api = WoHomeApi(None, "station.example", 8080)
    url = "http://ha.example/api/camera_proxy_stream/camera.door?interval=1&authSig=example"

    asyncio.run(api.open_camera("", "Door", 30, mjpeg_url=url))

    put_json.assert_awaited_once_with("/camera", {"url": "", "title": "Door", "duration": 30, "mjpeg_url": url})


@pytest.mark.parametrize("webrtc_url", [None, "http://ha.example/camera/webrtc?authSig=example"])
def test_camera_api_command(webrtc_url, station_tls):
    async def exercise():
        bodies = []
        action = {"id": "a" * 32, "label": "Entry light"} if webrtc_url else None

        async def handler(request):
            bodies.append((request.path, await request.json()))
            return web.json_response({}, status=202)

        async def action_handler(request):
            assert request.headers["Authorization"] == "Bearer test-key"
            payload = await request.json()
            bodies.append((request.path, payload))
            return web.Response(status=204) if "accepted" in payload else web.json_response({"status": "pressed"})

        app = web.Application()
        app.router.add_put("/api/v2/camera", handler)
        app.router.add_post("/api/v2/camera/action", action_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        context, _, fingerprint = station_tls
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                api = WoHomeApi(session, "127.0.0.1", port, "test-key", fingerprint)
                await api.open_camera("http://ha.example/stream.m3u8", "Door", 30, webrtc_url=webrtc_url, action=action)
                if action:
                    assert await api.poll_camera_action(action["id"]) == "pressed"
                    await api.finish_camera_action(action["id"], True)
            expected = {"url": "http://ha.example/stream.m3u8", "title": "Door", "duration": 30}
            if webrtc_url is not None:
                expected["webrtc_url"] = webrtc_url
            if action:
                expected["action"] = action
            expected_requests = [("/api/v2/camera", expected)]
            if action:
                expected_requests.extend([
                    ("/api/v2/camera/action", {"id": action["id"]}),
                    ("/api/v2/camera/action", {"id": action["id"], "accepted": True}),
                ])
            assert bodies == expected_requests
        finally:
            await runner.cleanup()

    asyncio.run(exercise())
