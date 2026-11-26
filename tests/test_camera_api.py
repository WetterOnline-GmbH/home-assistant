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
def test_camera_api_command(webrtc_url):
    async def exercise():
        bodies = []

        async def handler(request):
            bodies.append((request.path, await request.json()))
            return web.json_response({}, status=202)

        app = web.Application()
        app.router.add_put("/api/v1/camera", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as session:
                api = WoHomeApi(session, "127.0.0.1", port)
                await api.open_camera("http://ha.example/stream.m3u8", "Door", 30, webrtc_url=webrtc_url)
            expected = {"url": "http://ha.example/stream.m3u8", "title": "Door", "duration": 30}
            if webrtc_url is not None:
                expected["webrtc_url"] = webrtc_url
            assert bodies == [("/api/v1/camera", expected)]
        finally:
            await runner.cleanup()

    asyncio.run(exercise())
