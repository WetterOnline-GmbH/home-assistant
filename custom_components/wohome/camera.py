from __future__ import annotations

import asyncio
from contextlib import suppress
import json

from aiohttp import web, WSMsgType
from webrtc_models import RTCIceCandidateInit

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.camera import async_request_stream, get_camera_from_entity_id
from homeassistant.components.http import HomeAssistantView, KEY_HASS_USER
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.ulid import ulid

from .dashboard import dashboard_url

CAMERA_WEBRTC_PATH = "/api/wohome/camera/{entity_id}/webrtc"


class WoHomeCameraView(HomeAssistantView):
    url = CAMERA_WEBRTC_PATH
    name = "api:wohome:camera"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        if not entity_id.startswith("camera.") or not request[KEY_HASS_USER].permissions.check_entity(entity_id, POLICY_READ):
            raise web.HTTPForbidden()
        try:
            camera = get_camera_from_entity_id(self.hass, entity_id)
        except HomeAssistantError:
            raise web.HTTPNotFound() from None
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=262144)
        if not ws.can_prepare(request).ok:
            try:
                async with asyncio.timeout(25):
                    path = await async_request_stream(self.hass, entity_id, "hls")
                    return web.json_response({"url": dashboard_url(self.hass, path)})
            except Exception:
                return web.json_response({"error": "stream_unavailable"}, status=400)

        await ws.prepare(request)
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
        session_id = ulid()
        offer_task: asyncio.Task | None = None
        pending_candidates: list[RTCIceCandidateInit] = []
        offer_ready = False

        @callback
        def send_message(message) -> None:
            data = message.as_dict()
            if data["type"] == "error":
                data = {"type": "error"}
            with suppress(asyncio.QueueFull):
                queue.put_nowait(data)

        async def send_messages() -> None:
            while True:
                await ws.send_json(await queue.get())

        async def handle_offer(sdp: str) -> None:
            nonlocal offer_ready
            try:
                await camera.async_handle_async_webrtc_offer(sdp, session_id, send_message)
                offer_ready = True
                for candidate in pending_candidates:
                    await camera.async_on_webrtc_candidate(session_id, candidate)
                pending_candidates.clear()
            except Exception:
                await queue.put({"type": "error"})

        sender = asyncio.create_task(send_messages())
        try:
            await ws.send_json({"type": "config", **camera.async_get_webrtc_client_configuration().to_frontend_dict()})
            async with asyncio.timeout(320):
                async for message in ws:
                    if message.type != WSMsgType.TEXT:
                        break
                    data = json.loads(message.data)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid signaling message")
                    if data.get("type") == "offer" and offer_task is None and isinstance(data.get("offer"), str):
                        offer_task = asyncio.create_task(handle_offer(data["offer"]))
                    elif data.get("type") == "candidate" and offer_task is not None:
                        candidate = RTCIceCandidateInit.from_dict(data["candidate"])
                        if offer_ready:
                            await camera.async_on_webrtc_candidate(session_id, candidate)
                        elif len(pending_candidates) < 64:
                            pending_candidates.append(candidate)
                    else:
                        await ws.close(code=1008)
                        break
        except Exception:
            await ws.close(code=1008)
        finally:
            tasks = [sender] + ([offer_task] if offer_task is not None else [])
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if offer_task is not None:
                camera.close_webrtc_session(session_id)
            await ws.close()
        return ws
