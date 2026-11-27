"""Run in the HA test container with python -m unittest test_dashboard_selection."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.lovelace.const import ConfigNotFound, EVENT_LOVELACE_UPDATED, LOVELACE_DATA
from homeassistant.core import Event

from custom_components.wohome.const import CONF_DASHBOARD_PATH
from custom_components.wohome.dashboard import async_dashboard_options, dashboard_url
from custom_components.wohome.select import WoHomeDashboardSelect


class DashboardSelectionTest(unittest.TestCase):
    def test_no_dashboard_option_clears_the_url(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="de"), data={})

        options = asyncio.run(async_dashboard_options(hass))
        self.assertEqual(options[0].label, "Kein Dashboard")
        self.assertEqual(options[0].path, "")
        with patch("custom_components.wohome.dashboard.get_url", side_effect=AssertionError("unexpected URL lookup")):
            self.assertEqual(dashboard_url(hass, ""), "")

    def test_dashboard_url_stays_unchanged_for_selected_dashboards(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="en"), data={})

        self.assertEqual(asyncio.run(async_dashboard_options(hass))[0].label, "No dashboard")
        with patch("custom_components.wohome.dashboard.get_url", return_value="http://ha.example:8123"):
            self.assertEqual(dashboard_url(hass, "/lovelace"), "http://ha.example:8123/lovelace")

    def test_dashboard_options_include_visible_tabs_and_keep_dashboard_roots(self):
        default = SimpleNamespace(config=None, async_load=AsyncMock(side_effect=ConfigNotFound))
        overview = SimpleNamespace(
            config={"url_path": "lovelace", "title": "Home"},
            async_load=AsyncMock(return_value={"views": [{"title": "Start", "path": "start"}]}),
        )
        house = SimpleNamespace(
            config={"url_path": "dashboard-house", "title": "House"},
            async_load=AsyncMock(return_value={"views": [
                {"title": "Entrance", "path": "entrance"},
                {"title": "Detail", "subview": True},
                {"title": "Hidden", "visible": False},
                {"title": "Energy"},
            ]}),
        )
        generated = SimpleNamespace(
            config={"url_path": "dashboard-generated", "title": "Generated"},
            async_load=AsyncMock(side_effect=ConfigNotFound),
        )
        hass = SimpleNamespace(
            config=SimpleNamespace(language="en"),
            data={LOVELACE_DATA: SimpleNamespace(dashboards={
                None: default, "lovelace": overview, "dashboard-house": house,
                "dashboard-generated": generated,
            })},
        )

        options = asyncio.run(async_dashboard_options(hass))

        self.assertEqual([(option.path, option.label) for option in options], [
            ("", "No dashboard"),
            ("/lovelace", "Overview (/lovelace)"),
            ("/lovelace/start", "Overview → Start (/lovelace/start)"),
            ("/dashboard-house", "House (/dashboard-house)"),
            ("/dashboard-house/entrance", "House → Entrance (/dashboard-house/entrance)"),
            ("/dashboard-house/3", "House → Energy (/dashboard-house/3)"),
            ("/dashboard-generated", "Generated (/dashboard-generated)"),
        ])

    def test_select_sends_tab_url_and_remembers_it_after_reload(self):
        async def exercise():
            dashboard = SimpleNamespace(
                config={"url_path": "dashboard-house", "title": "House"},
                async_load=AsyncMock(return_value={"views": [{"title": "Entrance", "path": "entrance"}]}),
            )
            coordinator = Mock(device_info={}, api=SimpleNamespace(set_dashboard=AsyncMock()))
            hass = SimpleNamespace(
                config=SimpleNamespace(language="en"),
                data={LOVELACE_DATA: SimpleNamespace(dashboards={"dashboard-house": dashboard})},
                bus=Mock(),
                config_entries=SimpleNamespace(
                    async_update_entry=lambda entry, *, options: setattr(entry, "options", options),
                ),
            )
            entry = SimpleNamespace(unique_id="station", options={}, data={})
            select = WoHomeDashboardSelect(hass, entry, coordinator)
            label = "House → Entrance (/dashboard-house/entrance)"

            await select.async_added_to_hass()
            self.assertEqual(select.current_option, "Overview (/lovelace)")
            with patch.object(select, "async_write_ha_state"), patch(
                "custom_components.wohome.dashboard.get_url", return_value="http://ha.example:8123"
            ):
                await select.async_handle_select_option(label)
            coordinator.api.set_dashboard.assert_awaited_once_with("http://ha.example:8123/dashboard-house/entrance")
            self.assertEqual(entry.options[CONF_DASHBOARD_PATH], "/dashboard-house/entrance")

            reloaded = WoHomeDashboardSelect(hass, entry, coordinator)
            await reloaded.async_added_to_hass()
            self.assertEqual(reloaded.current_option, label)

            listener = next(
                call.args[1] for call in reversed(hass.bus.async_listen.call_args_list)
                if call.args[0] == EVENT_LOVELACE_UPDATED
            )
            dashboard.async_load.return_value["views"][0]["title"] = "Front door"
            with patch.object(reloaded, "async_write_ha_state") as write_state:
                await listener(Event(EVENT_LOVELACE_UPDATED))
            write_state.assert_called_once()
            self.assertEqual(reloaded.current_option, "House → Front door (/dashboard-house/entrance)")

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
