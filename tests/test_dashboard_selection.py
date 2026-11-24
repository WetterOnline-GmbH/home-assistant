"""Run in the HA test container with python -m unittest test_dashboard_selection."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.wohome.const import CONF_DASHBOARD_MODE, CONF_DASHBOARD_PATH, MANUAL_DASHBOARD
from custom_components.wohome.dashboard import dashboard_options, dashboard_url
from custom_components.wohome.select import WoHomeDashboardSelect
from custom_components.wohome.text import WoHomeDashboardText
from homeassistant.exceptions import HomeAssistantError


class DashboardSelectionTest(unittest.TestCase):
    def test_no_dashboard_option_clears_the_url(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="de"), data={})

        self.assertEqual(dashboard_options(hass)[0].label, "Kein Dashboard")
        self.assertEqual(dashboard_options(hass)[0].path, "")
        with patch("custom_components.wohome.dashboard.get_url", side_effect=AssertionError("unexpected URL lookup")):
            self.assertEqual(dashboard_url(hass, ""), "")

    def test_dashboard_url_stays_unchanged_for_selected_dashboards(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="en"), data={})

        self.assertEqual(dashboard_options(hass)[0].label, "No dashboard")
        with patch("custom_components.wohome.dashboard.get_url", return_value="http://ha.example:8123"):
            self.assertEqual(dashboard_url(hass, "/lovelace"), "http://ha.example:8123/lovelace")

    def test_manual_url_and_invalid_urls(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="en"), data={})
        self.assertEqual(dashboard_options(hass)[-1].label, "Manual")
        self.assertEqual(dashboard_url(hass, "https://example.org/board"), "https://example.org/board")
        for value in ("javascript:alert(1)", "//example.org", "https://user:pass@example.org",
                      "https://example.org:invalid", "https://example.org/#secret", "example.org"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dashboard_url(hass, value)


class DashboardSelectionFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_select_manual_then_none_or_dashboard(self):
        entry = SimpleNamespace(data={CONF_DASHBOARD_PATH: "/lovelace"}, options={})
        api = SimpleNamespace(set_dashboard=AsyncMock())
        coordinator = SimpleNamespace(api=api, async_update_listeners=MagicMock())
        entries = SimpleNamespace(async_update_entry=MagicMock(side_effect=lambda _, options: setattr(entry, "options", options)))
        hass = SimpleNamespace(config=SimpleNamespace(language="en"), data={}, config_entries=entries)
        select = WoHomeDashboardSelect.__new__(WoHomeDashboardSelect)
        select._hass, select._entry, select.coordinator = hass, entry, coordinator
        text = WoHomeDashboardText.__new__(WoHomeDashboardText)
        text._hass, text._entry, text.coordinator = hass, entry, coordinator
        with patch("custom_components.wohome.dashboard.get_url", return_value="http://ha.example:8123"):
            self.assertEqual(text.native_value, "/lovelace")
            with self.assertRaises(HomeAssistantError):
                await text.async_set_value("https://example.org/board")
            api.set_dashboard.assert_not_awaited()

            await select.async_select_option("Manual")
            self.assertEqual(select.current_option, "Manual")
            self.assertEqual(entry.options[CONF_DASHBOARD_MODE], MANUAL_DASHBOARD)
            api.set_dashboard.assert_awaited_with("http://ha.example:8123/lovelace")

            await text.async_set_value("https://example.org/board")
            self.assertEqual(text.native_value, "https://example.org/board")
            api.set_dashboard.assert_awaited_with("https://example.org/board")
            coordinator.async_update_listeners.assert_called()

            await select.async_select_option("No dashboard")
            self.assertEqual(select.current_option, "No dashboard")
            self.assertEqual(entry.options[CONF_DASHBOARD_PATH], "")
            self.assertEqual(text.native_value, "")
            self.assertNotIn(CONF_DASHBOARD_MODE, entry.options)
            api.set_dashboard.assert_awaited_with("")

            await select.async_select_option("Overview (/lovelace)")
            self.assertEqual(select.current_option, "Overview (/lovelace)")
            self.assertEqual(entry.options[CONF_DASHBOARD_PATH], "/lovelace")
            self.assertEqual(text.native_value, "/lovelace")

    async def test_manual_url_is_persisted_only_after_device_accepts_it(self):
        api = SimpleNamespace(set_dashboard=AsyncMock())
        entry = SimpleNamespace(data={}, options={CONF_DASHBOARD_MODE: MANUAL_DASHBOARD})
        entries = SimpleNamespace(async_update_entry=MagicMock(side_effect=lambda _, options: setattr(entry, "options", options)))
        hass = SimpleNamespace(config_entries=entries)
        coordinator = SimpleNamespace(api=api, async_update_listeners=MagicMock())
        text = WoHomeDashboardText.__new__(WoHomeDashboardText)
        text._hass, text._entry, text.coordinator = hass, entry, coordinator
        with patch("custom_components.wohome.dashboard.get_url", return_value="http://ha.example:8123"):
            await text.async_set_value("https://example.org/board")
            api.set_dashboard.assert_awaited_once_with("https://example.org/board")
            self.assertEqual(entry.options[CONF_DASHBOARD_PATH], "https://example.org/board")
            api.set_dashboard.side_effect = OSError("offline")
            with self.assertRaises(HomeAssistantError):
                await text.async_set_value("/another")
            with self.assertRaises(HomeAssistantError):
                await text.async_set_value("javascript:alert(1)")
            self.assertEqual(entries.async_update_entry.call_count, 1)
            self.assertEqual(text.native_value, "https://example.org/board")


if __name__ == "__main__":
    unittest.main()
