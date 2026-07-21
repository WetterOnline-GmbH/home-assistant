"""Stub API client for the WetterOnline cloud weather service.

STUB CLIENT — the WetterOnline HTTP API does not exist yet. Every method
returns placeholder data and makes no network request. Replace each
`# TODO(api)` block with the real aiohttp call once the endpoint and token
support ship.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession

_STUB = True


class WetterOnlineError(Exception):
    """Base error for the WetterOnline API client."""


class WetterOnlineAuthError(WetterOnlineError):
    """Raised when the API key is invalid or has been revoked."""


class WetterOnlineConnectionError(WetterOnlineError):
    """Raised when the WetterOnline service cannot be reached."""


@dataclass(frozen=True)
class Location:
    """A single WetterOnline location."""

    id: str
    lat: float
    lon: float
    label: str


@dataclass(frozen=True)
class WeatherData:
    """Current conditions plus daily/hourly forecast for a location."""

    current: dict[str, Any]
    daily: list[dict[str, Any]]
    hourly: list[dict[str, Any]]


class WetterOnlineApiClient:
    """Client for the (future) WetterOnline HTTP API.

    Every method below is a stand-in: it validates nothing over the wire,
    performs no I/O, and returns clearly-labeled placeholder data so the rest
    of the integration (config flow, coordinator, weather entity) can be
    built and exercised end-to-end before the real API exists.
    """

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Store the shared client session and the account API key."""
        self._session = session
        self._api_key = api_key

    async def async_validate_key(self) -> dict[str, Any]:
        """Validate the API key and return basic account info."""
        # TODO(api): GET /account with an "Authorization: Bearer <api_key>"
        # header via self._session. Raise WetterOnlineAuthError on HTTP 401,
        # and WetterOnlineConnectionError on network errors or HTTP 5xx.
        return {"tier": "premium"}

    async def async_search_location(self, query: str) -> list[Location]:
        """Search for a location by free-text query."""
        # TODO(api): GET /geocode?q=<query> via self._session, authenticated
        # with self._api_key. Parse the JSON response into a list of
        # Location objects, raising WetterOnlineConnectionError on failure.
        return [
            Location(
                id="DE0001020",
                lat=50.11,
                lon=8.68,
                label=f"{query} (placeholder)",
            )
        ]

    async def async_get_weather(self, location: Location) -> WeatherData:
        """Fetch current conditions plus daily/hourly forecast."""
        # TODO(api): GET /weather?lat={location.lat}&lon={location.lon} via
        # self._session, authenticated with self._api_key. Parse the JSON
        # response into current/daily/hourly dicts, raising
        # WetterOnlineAuthError on 401 and WetterOnlineConnectionError on
        # network errors or HTTP 5xx.
        return WeatherData(
            current={
                "temperature": 21.0,
                "humidity": 60,
                "pressure": 1013,
                "wind_speed": 12,
                "wind_bearing": 180,
                "condition_code": "2",
            },
            daily=[
                {
                    "datetime": "2026-07-20T00:00:00+00:00",
                    "temperature": 24.0,
                    "templow": 15.0,
                    "condition_code": "2",
                },
                {
                    "datetime": "2026-07-21T00:00:00+00:00",
                    "temperature": 22.0,
                    "templow": 14.0,
                    "condition_code": "4",
                },
            ],
            hourly=[
                {
                    "datetime": "2026-07-20T12:00:00+00:00",
                    "temperature": 21.0,
                    "condition_code": "2",
                },
                {
                    "datetime": "2026-07-20T13:00:00+00:00",
                    "temperature": 21.5,
                    "condition_code": "1",
                },
            ],
        )
