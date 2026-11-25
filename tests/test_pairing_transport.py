"""Exercise initial pairing and reauthentication against a local HTTPS station."""

import asyncio
import hashlib
import secrets
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aiohttp import ClientSession, ServerFingerprintMismatch, web
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.wohome.api import WoHomeApi
from custom_components.wohome.config_flow import WoHomeConfigFlow
from custom_components.wohome.const import API_PATH
from custom_components.wohome.coordinator import WoHomeCoordinator


async def check(station_tls) -> None:
    context, der, fingerprint = station_tls
    state: dict[str, str] = {}

    async def info(request):
        return web.json_response({"id": state.get("id", "test"), "api_version": 2})

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
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
        await site.start()
        try:
            port = site._server.sockets[0].getsockname()[1]
            async with ClientSession() as session:
                api = WoHomeApi(session, "127.0.0.1", port)
                assert (await api.get_info())["id"] == "test"
                with pytest.raises(ConfigEntryAuthFailed) as exc:
                    await WoHomeCoordinator._async_update_data(SimpleNamespace(api=api))
                assert exc.value.translation_key == "pairing_required"
                nonce = secrets.token_urlsafe(32)
                ticket, observed_cert = await api.start_pairing(nonce)
                assert observed_cert == der
                assert hashlib.sha256(observed_cert + nonce.encode("ascii") + ticket.encode("ascii")).digest()[:6] == \
                    hashlib.sha256(der + state["nonce"].encode("ascii") + state["ticket"].encode("ascii")).digest()[:6]
                secret = secrets.token_urlsafe(32)
                entry_data = {"host": "127.0.0.1", "port": port, "name": "Test station"}
                flow = WoHomeConfigFlow()
                flow.context = {"source": SOURCE_USER}
                flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
                flow._discovered_values = entry_data
                with patch.object(flow, "_set_confirm_only"), patch(
                    "custom_components.wohome.config_flow.async_get_clientsession", return_value=session
                ), patch("custom_components.wohome.config_flow.secrets.token_urlsafe", return_value=secret):
                    assert (await flow.async_step_pairing())["step_id"] == "pairing"
                    created = await flow.async_step_pairing({})
                assert created["type"] is FlowResultType.CREATE_ENTRY
                assert created["data"] == {**entry_data, "key": secret, "fingerprint": fingerprint}
                paired = WoHomeApi(session, "127.0.0.1", port, secret, fingerprint)
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
                with pytest.raises(ServerFingerprintMismatch):
                    await wrong.get_state()
                with pytest.raises(UpdateFailed):
                    await WoHomeCoordinator._async_update_data(SimpleNamespace(api=wrong))
                with pytest.raises(ValueError, match="does not match"):
                    await wrong.start_pairing(nonce)
                await paired.revoke()
                with pytest.raises(ConfigEntryAuthFailed):
                    await WoHomeCoordinator._async_update_data(SimpleNamespace(api=paired))

                entry = SimpleNamespace(
                    entry_id="existing", unique_id="test", title="Test station",
                    data=created["data"], update_listeners=[],
                )
                entries = Mock()
                entries.async_get_known_entry.return_value = entry
                flow = WoHomeConfigFlow()
                flow.context = {"source": SOURCE_REAUTH, "entry_id": entry.entry_id}
                flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"), config_entries=entries)
                with patch.object(flow, "_set_confirm_only"), patch(
                    "custom_components.wohome.config_flow.async_get_clientsession", return_value=session
                ):
                    assert (await flow.async_step_reauth(entry.data))["step_id"] == "reauth_confirm"
                    state["id"] = "different-device"
                    assert (await flow.async_step_reauth_confirm({}))["reason"] == "wrong_device"
                    del state["id"]
                    entries.async_update_entry.assert_not_called()
                    assert (await flow.async_step_reauth_confirm({}))["step_id"] == "pairing"
                    entries.async_update_entry.assert_not_called()
                    assert (await flow.async_step_pairing({}))["reason"] == "reauth_successful"
                update = entries.async_update_entry.call_args.kwargs
                assert update["entry"] is entry
                new_key = update["data"]["key"]
                assert new_key != secret
                assert update["data"] == {**entry.data, "key": new_key}
                entries.async_schedule_reload.assert_called_once_with(entry.entry_id)
                assert (await WoHomeApi(session, "127.0.0.1", port, new_key, fingerprint).get_state())["ok"]
        finally:
            await site.stop()
    finally:
        await runner.cleanup()
    with pytest.raises(UpdateFailed):
        async with ClientSession() as session:
            offline = WoHomeApi(session, "127.0.0.1", port, secret, fingerprint)
            await WoHomeCoordinator._async_update_data(SimpleNamespace(api=offline))


def test_pairing_transport(station_tls):
    asyncio.run(check(station_tls))
