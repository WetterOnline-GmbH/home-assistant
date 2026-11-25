"""Check that support diagnostics redact credentials and identifying data."""

import asyncio
from types import SimpleNamespace

from custom_components.wohome.diagnostics import async_get_config_entry_diagnostics


def test_diagnostics_redact_identifying_data():
    private = {
        "host": "example.invalid",
        "key": "synthetic-device-credential",
        "fingerprint": "synthetic-fingerprint",
        "id": "synthetic-device-id",
        "name": "synthetic-device-name",
        "dashboard_path": "/synthetic-dashboard",
    }
    entry = SimpleNamespace(
        data=private,
        options={"dashboard_path": private["dashboard_path"]},
        runtime_data=SimpleNamespace(coordinator=SimpleNamespace(
            info={"id": private["id"], "name": private["name"], "api_version": 2},
            data={"display": {"is_on": True}},
        )),
    )

    result = asyncio.run(async_get_config_entry_diagnostics(None, entry))

    assert all(value not in repr(result) for value in private.values())
    assert result["info"]["api_version"] == 2
    assert result["data"]["display"]["is_on"] is True
