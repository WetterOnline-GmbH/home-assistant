"""Keep the pairing code visible even when frontend translations are stale."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError

from custom_components.wohome.config_flow import WoHomeConfigFlow


def test_pairing_code_visible_without_translation_on_initial_and_retry_forms():
    api = SimpleNamespace(
        start_pairing=AsyncMock(return_value=("ticket", b"test certificate")),
        complete_pairing=AsyncMock(side_effect=ClientError("not confirmed")),
    )
    flow = WoHomeConfigFlow()
    flow.hass = None
    flow._discovered_values = {"host": "example.invalid", "port": 8080}

    with patch.object(flow, "_set_confirm_only"), patch(
        "custom_components.wohome.config_flow.async_get_clientsession", return_value=object()
    ), patch("custom_components.wohome.config_flow.WoHomeApi", return_value=api):
        first = asyncio.run(flow.async_step_pairing())
        code = first["description_placeholders"]["code"]
        assert first["data_schema"]({}) == {}
        label = next(iter(first["data_schema"].schema.values())).config["label"]
        assert code in label and "Only continue if they match" in label

        retry = asyncio.run(flow.async_step_pairing({}))
        assert retry["errors"]["base"] == "not_confirmed"
        assert retry["description_placeholders"]["code"] == code
        assert retry["data_schema"]({}) == {}
        assert code in next(iter(retry["data_schema"].schema.values())).config["label"]


def test_discovery_confirmation_visible_without_translation():
    flow = WoHomeConfigFlow()
    flow._discovered_values = {"name": "Test station"}
    with patch.object(flow, "_set_confirm_only"):
        form = asyncio.run(flow.async_step_zeroconf_confirm())
    assert form["data_schema"]({}) == {}
    assert "Test station" in next(iter(form["data_schema"].schema.values())).config["label"]
