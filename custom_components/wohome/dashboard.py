from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DEFAULT_DASHBOARD_PATH


@dataclass(frozen=True)
class DashboardOption:
    path: str
    label: str


def dashboard_options(hass: HomeAssistant) -> list[DashboardOption]:
    options: list[DashboardOption] = []
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
            0,
            DashboardOption(
                path=DEFAULT_DASHBOARD_PATH,
                label="Overview (/lovelace)",
            ),
        )
    return options


def dashboard_url(hass: HomeAssistant, dashboard_path: str) -> str:
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
