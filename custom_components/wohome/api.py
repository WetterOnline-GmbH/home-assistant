from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import API_PATH


class WoHomeApi:
    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        self._session = session
        self._host = host.rstrip("/")
        self._port = port
        self._timeout = ClientTimeout(total=10)

    def _url(self, path: str) -> str:
        return f"http://{self._host}:{self._port}{API_PATH}{path}"

    async def _get_json(self, path: str) -> dict[str, Any]:
        async with self._session.get(self._url(path), timeout=self._timeout) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _put_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with self._session.put(
            self._url(path), json=body, timeout=self._timeout
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def get_info(self) -> dict[str, Any]:
        return await self._get_json("/info")

    async def get_state(self) -> dict[str, Any]:
        return await self._get_json("/state")

    async def set_display(self, is_on: bool) -> None:
        await self._put_json("/display", {"is_on": is_on})

    async def set_dashboard(self, url: str) -> None:
        await self._put_json("/dashboard", {"url": url})
