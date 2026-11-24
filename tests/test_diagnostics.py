"""Check that support diagnostics never contain the device credential."""

import asyncio
from types import SimpleNamespace

from custom_components.wohome.diagnostics import async_get_config_entry_diagnostics


def test_diagnostics_redact_device_credential():
    credential = "synthetic-device-credential"
    entry = SimpleNamespace(
        data={"host": "example.invalid", "key": credential, "fingerprint": "public"},
        options={"dashboard_path": "https://example.org/private?token=synthetic-secret"},
        runtime_data=SimpleNamespace(coordinator=SimpleNamespace(info={}, data={})),
    )

    result = asyncio.run(async_get_config_entry_diagnostics(None, entry))

    assert credential not in repr(result)
    assert result["entry_data"]["key"] != credential
    assert result["entry_data"]["host"] != "example.invalid"
    assert "synthetic-secret" not in repr(result)
