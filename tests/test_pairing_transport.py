"""Run in the Home Assistant test container: python /config/test_pairing_transport.py."""

import asyncio
import datetime
import hashlib
import secrets
import ssl
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientSession, ServerFingerprintMismatch, web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from homeassistant.exceptions import ConfigEntryError

from custom_components.wohome.api import WoHomeApi
from custom_components.wohome.config_flow import WoHomeConfigFlow
from custom_components.wohome.const import API_PATH
from custom_components.wohome.coordinator import WoHomeCoordinator


async def check() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "WOHome test")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    der = cert.public_bytes(serialization.Encoding.DER)
    state: dict[str, str] = {}

    async def info(request):
        return web.json_response({"id": "test", "api_version": 2})

    async def start(request):
        if state.get("key"):
            return web.Response(status=409)
        state["nonce"] = (await request.json())["nonce"]
        state["ticket"] = secrets.token_urlsafe(32)
        return web.json_response({"ticket": state["ticket"]})

    async def complete(request):
        body = await request.json()
        assert body["ticket"] == state["ticket"]
        state["key"] = body["key"]
        return web.Response(status=204)

    async def get_state(request):
        if request.headers.get("Authorization") != f"Bearer {state.get('key')}":
            return web.Response(status=401)
        return web.json_response({"ok": True})

    async def revoke(request):
        if request.headers.get("Authorization") != f"Bearer {state.get('key')}":
            return web.Response(status=401)
        state.pop("key")
        return web.Response(status=204)

    app = web.Application()
    app.add_routes([web.get(f"{API_PATH}/info", info), web.post(f"{API_PATH}/pairing/start", start),
                    web.post(f"{API_PATH}/pairing/complete", complete), web.get(f"{API_PATH}/state", get_state),
                    web.post(f"{API_PATH}/pairing/revoke", revoke)])
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        Path(tmp, "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(Path(tmp, "cert.pem")), str(Path(tmp, "key.pem")))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
        await site.start()
        try:
            port = site._server.sockets[0].getsockname()[1]
            async with ClientSession() as session:
                api = WoHomeApi(session, "127.0.0.1", port)
                assert (await api.get_info())["id"] == "test"
                try:
                    await WoHomeCoordinator._async_update_data(SimpleNamespace(api=api))
                    raise AssertionError("missing credential accepted")
                except ConfigEntryError as error:
                    assert error.translation_key == "pairing_required"
                nonce = secrets.token_urlsafe(32)
                ticket, observed_cert = await api.start_pairing(nonce)
                assert observed_cert == der
                assert hashlib.sha256(observed_cert + nonce.encode("ascii") + ticket.encode("ascii")).digest()[:6] == \
                    hashlib.sha256(der + state["nonce"].encode("ascii") + state["ticket"].encode("ascii")).digest()[:6]
                secret = secrets.token_urlsafe(32)
                await api.complete_pairing(ticket, secret, observed_cert)
                paired = WoHomeApi(session, "127.0.0.1", port, secret, hashlib.sha256(der).hexdigest())
                assert (await paired.get_state())["ok"]
                flow = WoHomeConfigFlow()
                flow.hass = None
                flow._discovered_values = {"host": "127.0.0.1", "port": port}
                with patch.object(flow, "_set_confirm_only"), patch(
                    "custom_components.wohome.config_flow.async_get_clientsession", return_value=session
                ):
                    result = await flow.async_step_pairing()
                assert result["reason"] == "pairing_unavailable"
                try:
                    await WoHomeApi(session, "127.0.0.1", port, secret).get_state()
                    raise AssertionError("credential sent without certificate pin")
                except ValueError:
                    pass
                wrong = WoHomeApi(session, "127.0.0.1", port, secret, "00" * 32)
                try:
                    await wrong.get_state()
                    raise AssertionError("wrong certificate accepted")
                except ServerFingerprintMismatch:
                    pass
                await paired.revoke()
                try:
                    await paired.get_state()
                    raise AssertionError("revoked credential accepted")
                except Exception as error:
                    assert "ClientResponseError" in type(error).__name__, type(error).__name__
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(check())
    print("HA Docker: HTTPS pairing transport and certificate pinning passed")
