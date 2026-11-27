from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urljoin

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DEFAULT_DASHBOARD_PATH


@dataclass(frozen=True)
class DashboardOption:
    path: str
    label: str


async def async_dashboard_options(hass: HomeAssistant) -> list[DashboardOption]:
    options = [DashboardOption("", "Kein Dashboard" if hass.config.language.startswith("de") else "No dashboard")]
    seen: set[str] = set()
    lovelace_data = hass.data.get(LOVELACE_DATA)
    dashboards = dict(lovelace_data.dashboards) if lovelace_data is not None else {}

    for dashboard in dashboards.values():
        config = dashboard.config or {}
        url_path = config.get("url_path") or "lovelace"
        path = f"/{url_path.lstrip('/')}"
        if path in seen:
            continue
        seen.add(path)
        title = config.get("title") or "Overview"
        options.append(DashboardOption(path=path, label=f"{title} ({path})"))

        # Lovelace prefers a registered /lovelace dashboard over its default storage config.
        if path == DEFAULT_DASHBOARD_PATH:
            dashboard = dashboards.get("lovelace", dashboard)
        try:
            content = await dashboard.async_load(force=False)
        except (HomeAssistantError, OSError):
            continue

        views = content.get("views")
        if content.get("strategy") or not isinstance(views, list):
            continue
        for index, view in enumerate(views):
            if not isinstance(view, dict) or view.get("subview") or view.get("visible") in (False, []):
                continue
            view_path = view.get("path") or str(index)
            if not isinstance(view_path, str) or view_path in {".", ".."} or "/" in view_path:
                continue
            target_path = f"{path}/{quote(view_path, safe='')}"
            if target_path in seen:
                continue
            seen.add(target_path)
            view_title = view.get("title") or view_path
            options.append(DashboardOption(target_path, f"{title} → {view_title} ({target_path})"))

    if DEFAULT_DASHBOARD_PATH not in seen:
        options.insert(
            1,
            DashboardOption(
                path=DEFAULT_DASHBOARD_PATH,
                label="Overview (/lovelace)",
            ),
        )
    return options


def dashboard_url(hass: HomeAssistant, dashboard_path: str) -> str:
    if not dashboard_path:
        return ""
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
