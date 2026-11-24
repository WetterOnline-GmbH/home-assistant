from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DEFAULT_DASHBOARD_PATH


@dataclass(frozen=True)
class DashboardOption:
    path: str | None
    label: str


def dashboard_options(hass: HomeAssistant) -> list[DashboardOption]:
    options = [DashboardOption("", "Kein Dashboard" if hass.config.language.startswith("de") else "No dashboard")]
    seen: set[str] = set()
    lovelace_data = hass.data.get(LOVELACE_DATA)
    dashboards = getattr(lovelace_data, "dashboards", {}).values()

    for dashboard in dashboards:
        config = dashboard.config or {}
        url_path = config.get("url_path") or "lovelace"
        path = f"/{url_path.lstrip('/')}"
        if path in seen:
            continue
        seen.add(path)
        title = config.get("title") or "Overview"
        options.append(DashboardOption(path=path, label=f"{title} ({path})"))

    if DEFAULT_DASHBOARD_PATH not in seen:
        options.insert(
            1,
            DashboardOption(
                path=DEFAULT_DASHBOARD_PATH,
                label="Overview (/lovelace)",
            ),
        )
    options.append(DashboardOption(None, "Manuell" if hass.config.language.startswith("de") else "Manual"))
    return options


def dashboard_url(hass: HomeAssistant, dashboard_path: str) -> str:
    if not dashboard_path:
        return ""
    if len(dashboard_path) > 2048 or any(ord(char) < 32 or char.isspace() for char in dashboard_path):
        raise ValueError("Invalid dashboard URL")
    parsed = urlsplit(dashboard_path)
    if parsed.fragment:
        raise ValueError("Invalid dashboard URL")
    if parsed.scheme or parsed.netloc:
        if (parsed.scheme.lower() not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError("Invalid dashboard URL")
        if parsed.port is not None and parsed.port not in range(1, 65536):
            raise ValueError("Invalid dashboard URL")
        return dashboard_path
    if not dashboard_path.startswith("/") or dashboard_path.startswith("//"):
        raise ValueError("Invalid dashboard path")
    try:
        base_url = get_url(
            hass,
            allow_internal=True,
            allow_external=False,
            allow_cloud=False,
        )
    except NoURLAvailableError:
        base_url = get_url(
            hass,
            allow_internal=False,
            allow_external=True,
            allow_cloud=False,
        )
    return urljoin(f"{base_url.rstrip('/')}/", dashboard_path.lstrip("/"))
