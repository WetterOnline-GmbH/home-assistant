"""Run in the HA test container with python -m unittest test_dashboard_selection."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.wohome.dashboard import dashboard_options, dashboard_url


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


if __name__ == "__main__":
    unittest.main()
