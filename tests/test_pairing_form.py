"""Keep the pairing code visible even when frontend translations are stale."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState, SOURCE_ZEROCONF
from homeassistant.data_entry_flow import AbortFlow
import pytest

from custom_components.wohome.config_flow import WoHomeConfigFlow


def test_pairing_code_visible_without_translation_on_initial_and_retry_forms():
    api = SimpleNamespace(
        start_pairing=AsyncMock(return_value=("ticket", b"test certificate")),
        complete_pairing=AsyncMock(side_effect=ClientError("not confirmed")),
    )
    flow = WoHomeConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="de"))
    flow._discovered_values = {"host": "example.invalid", "port": 8080}

    with patch.object(flow, "_set_confirm_only"), patch(
        "custom_components.wohome.config_flow.async_get_clientsession", return_value=object()
    ), patch("custom_components.wohome.config_flow.WoHomeApi", return_value=api):
        first = asyncio.run(flow.async_step_pairing())
        code = next(iter(first["data_schema"].schema.values())).config["value"]
        assert first["data_schema"]({}) == {}
        selector = next(iter(first["data_schema"].schema.values()))
        assert selector.config == {"value": code}
        assert first["description_placeholders"]["code"] == "den unten angezeigten Code"
        assert code not in first["description_placeholders"]["code"]

        retry = asyncio.run(flow.async_step_pairing({}))
        assert retry["errors"]["base"] == "not_confirmed"
        assert retry["description_placeholders"]["code"] == "den unten angezeigten Code"
        assert retry["data_schema"]({}) == {}
        assert next(iter(retry["data_schema"].schema.values())).config == {"value": code}

        flow.hass.config.language = "en"
        english = flow._pairing_form(code)
        assert english["description_placeholders"]["code"] == "the code below"


def test_discovery_confirmation_visible_without_translation():
    flow = WoHomeConfigFlow()
    flow._discovered_values = {"name": "Test station"}
    with patch.object(flow, "_set_confirm_only"):
        form = asyncio.run(flow.async_step_zeroconf_confirm())
    assert form["data_schema"]({}) == {}
    assert next(iter(form["data_schema"].schema.values())).config == {"value": "Test station"}


def test_rediscovery_updates_address_and_reloads_existing_entry():
    entry = SimpleNamespace(
        entry_id="existing", source=SOURCE_ZEROCONF, state=ConfigEntryState.LOADED,
        update_listeners=[],
        data={"host": "192.0.2.1", "port": 8080, "key": "test-key", "fingerprint": "test-pin"},
    )
    entries = Mock()
    entries.flow.async_progress_by_handler.return_value = []
    entries.async_entry_for_domain_unique_id.return_value = entry
    entries.async_update_entry.return_value = True
    flow = WoHomeConfigFlow()
    flow.handler = "wohome"
    flow.context = {"source": SOURCE_ZEROCONF}
    flow.hass = SimpleNamespace(config_entries=entries)
    discovery = SimpleNamespace(
        host="192.0.2.2", port=8080,
        properties={"id": "test-id", "model": "WOH4", "manufacturer": "WetterOnline"},
    )

    with pytest.raises(AbortFlow) as exc:
        asyncio.run(flow.async_step_zeroconf(discovery))

    assert exc.value.reason == "already_configured"
    entries.async_update_entry.assert_called_once_with(entry, data={**entry.data, "host": "192.0.2.2"})
    entries.async_schedule_reload.assert_called_once_with(entry.entry_id)
