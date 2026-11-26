from __future__ import annotations

from typing import Any
import asyncio
import ssl

from aiohttp import ClientSession, ClientTimeout, Fingerprint
import hashlib

from .const import API_PATH


class WoHomeApi:
    def __init__(self, session: ClientSession, host: str, port: int,
                 key: str | None = None, fingerprint: str | None = None) -> None:
        self._session = session
        self._host = host.rstrip("/")
        self._port = port
        self._timeout = ClientTimeout(total=10)
        self._key = key
        self._fingerprint = bytes.fromhex(fingerprint) if fingerprint else None

    def _url(self, path: str) -> str:
        return f"https://{self._host}:{self._port}{API_PATH}{path}"

    def _ssl(self) -> Fingerprint | bool:
        if self._key and self._fingerprint is None:
            raise ValueError("A device credential requires a pinned certificate")
        return Fingerprint(self._fingerprint) if self._fingerprint else False

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"} if self._key else {}

    async def _get_json(self, path: str) -> dict[str, Any]:
        async with self._session.get(self._url(path), timeout=self._timeout,
                                     ssl=self._ssl(), headers=self._headers()) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _put_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with self._session.put(
            self._url(path), json=body, timeout=self._timeout,
            ssl=self._ssl(), headers=self._headers(),
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def get_info(self) -> dict[str, Any]:
        return await self._get_json("/info")

    async def start_pairing(self, nonce: str) -> tuple[str, bytes]:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        async with asyncio.timeout(self._timeout.total):
            _, writer = await asyncio.open_connection(self._host, self._port, ssl=context)
            try:
                certificate = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
            finally:
                writer.close()
                await writer.wait_closed()
        digest = hashlib.sha256(certificate).digest()
        if self._fingerprint is not None and digest != self._fingerprint:
            raise ValueError("The pairing certificate does not match the stored fingerprint")
        async with self._session.post(self._url("/pairing/start"), json={"nonce": nonce},
                                      timeout=self._timeout,
                                      ssl=Fingerprint(digest)) as response:
            response.raise_for_status()
            data = await response.json()
            return data["ticket"], certificate

    async def complete_pairing(self, ticket: str, key: str, certificate: bytes) -> None:
        digest = hashlib.sha256(certificate).digest()
        async with self._session.post(self._url("/pairing/complete"),
                                      json={"ticket": ticket, "key": key},
                                      timeout=self._timeout, ssl=Fingerprint(digest)) as response:
            response.raise_for_status()

    async def revoke(self) -> None:
        async with self._session.post(self._url("/pairing/revoke"),
                                      timeout=self._timeout, ssl=self._ssl(),
                                      headers=self._headers()) as response:
            response.raise_for_status()

    async def get_state(self) -> dict[str, Any]:
        return await self._get_json("/state")

    async def set_display(self, is_on: bool) -> None:
        await self._put_json("/display", {"is_on": is_on})

    async def set_brightness(self, brightness: int) -> None:
        await self._put_json("/brightness", {"brightness": brightness})

    async def set_auto_brightness(self, enabled: bool) -> None:
        await self._put_json("/auto_brightness", {"enabled": enabled})

    async def set_dashboard(self, url: str) -> None:
        await self._put_json("/dashboard", {"url": url})

    async def open_camera(
        self, url: str, title: str, duration: int, *,
        webrtc_url: str | None = None, mjpeg_url: str | None = None,
    ) -> None:
        body = {"url": url, "title": title, "duration": duration}
        if webrtc_url is not None:
            body["webrtc_url"] = webrtc_url
        if mjpeg_url is not None:
            body["mjpeg_url"] = mjpeg_url
        await self._put_json("/camera", body)
