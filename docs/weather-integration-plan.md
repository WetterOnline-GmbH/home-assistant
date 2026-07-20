# Plan: WetterOnline Weather integration

This document proposes a **second, separate** Home Assistant integration that
exposes WetterOnline forecast data (the data the WoHome station pulls from our
servers) directly to Home Assistant — independent of whether the user owns a
WoHome station.

It is deliberately kept apart from the existing `wohome` device integration.
`wohome` represents *a device on the local network* (indoor sensors, screen,
dashboard). Weather for a location is *a cloud service*, not a property of that
device. Modeling them separately is the Home Assistant convention (Met.no,
AccuWeather, OpenWeatherMap, etc. are all standalone cloud-weather
integrations) and avoids the coupling problems of routing forecast data through
the tablet: duplicate weather when multiple stations exist, station location ≠
home location, and no weather at all for users without a station.

## 1. Domain and scope

- **Domain:** `wetteronline`
- **iot_class:** `cloud_polling`
- **integration_type:** `service`
- **Auth:** API key (paid account), validated during the config flow.
- **Primary entity:** one `weather` entity per configured location.
- Optional companion `sensor` entities for values that do not fit the weather
  entity model (e.g. UV index, pollen, precipitation probability) — added later,
  not in the first release.

Both integrations should share a **WetterOnline brand** entry in
home-assistant/brands so users searching "WetterOnline" discover both.

## 2. Config flow

Two independent entry paths, plus reconfigure/reauth:

### a. Manual (works for everyone, station or not)
1. `async_step_user`: enter **API key**.
2. Validate the key against our API (a lightweight `GET /account` or equivalent).
   - Invalid key → `error: invalid_auth`.
   - Network/5xx → `error: cannot_connect`.
3. `async_step_location`: pick the location. Default the latitude/longitude to
   Home Assistant's configured home coordinates (`hass.config.latitude/longitude`)
   so most users just confirm. Allow overriding via a location search
   (`GET /geocode?q=...`) or raw coordinates.
4. Create the entry. `unique_id` = our stable location id (or a rounded
   `lat,lon`) so the same location can't be added twice, but multiple *different*
   locations are allowed as separate entries.

### b. Discovery via the WoHome station (convenience path — point 3)
This is where path 1's "no setup" benefit is preserved **without** making the
station the data path.

Design on the device side (new local WoHome API surface, versioned under
`/api/v1`):

- `GET /api/v1/weather-service` returns, when the user has enabled it in the
  station's developer settings:
  ```json
  {
    "api_key": "wo_live_...",          // a scoped, revocable token, NOT the raw account key
    "location": { "id": "DE0001020", "lat": 50.11, "lon": 8.68, "label": "Frankfurt am Main" },
    "account_tier": "premium"
  }
  ```
  - The token should be **device-scoped and revocable** from the user's
    WetterOnline account (so losing the tablet doesn't leak the master key),
    with a documented rate-limit tier.
  - Endpoint returns `404`/`403` when the feature is disabled, so the station
    integration can silently skip discovery.

Flow:
1. The existing `wohome` integration, after it finishes setup, calls
   `GET /api/v1/weather-service`. If it returns credentials, it triggers a
   discovery flow for the `wetteronline` domain
   (`hass.config_entries.flow.async_init("wetteronline", context={"source": "integration_discovery"}, data={...})`).
2. `async_step_integration_discovery` in the `wetteronline` flow pre-fills the
   API key and location and shows a **confirm-only** step:
   "WetterOnline Weather discovered via your WoHome station. Add it?"
3. The user can still change the location before confirming (solves the
   "station is set to a different city" problem — HA is the source of truth once
   configured).

Result: station owners get near-zero-setup weather; non-owners use the manual
API-key path; multiple stations do not create duplicate weather entities
because the weather entry is keyed by location, not by station.

### c. Reauth / reconfigure
- `async_step_reauth` when the API returns 401 (expired/revoked key).
- `async_step_reconfigure` to change location or key without deleting the entry.
- An **options flow** for polling interval and units, within the limits allowed
  by the account tier.

## 3. Data layer

- `WetterOnlineApiClient` (async, uses `async_get_clientsession`), methods like
  `async_validate_key()`, `async_get_current(location)`,
  `async_get_forecast_daily(location)`, `async_get_forecast_hourly(location)`.
- One `DataUpdateCoordinator` per config entry.
  - **Polling interval must respect the account tier** and be enforced/derived
    server-side; document it. Default conservatively (e.g. 15–30 min) to protect
    the paid quota — HA users notice throttling.
  - Map HTTP 401 → `ConfigEntryAuthFailed` (triggers reauth), 4xx config errors →
    `ConfigEntryError`, transient/5xx → `UpdateFailed`.
- Requirements: publish a small `wetteronline` PyPI client and list it in
  `manifest.json` `requirements` (core does not allow vendored/embedded API code
  or `requirements: []` for a cloud service). Pin the version.

## 4. Weather entity

- Subclass `WeatherEntity` (a `CoordinatorEntity`).
- Advertise `WeatherEntityFeature.FORECAST_DAILY` and `FORECAST_HOURLY`.
- Implement `async_forecast_daily()` / `async_forecast_hourly()` (the modern
  subscription-based forecast API — do **not** put forecasts in extra state
  attributes, that pattern is deprecated).
- Report native units (`native_temperature`, `native_pressure`,
  `native_wind_speed`, …) and let HA convert; set
  `attribution = "Weather data provided by WetterOnline"`.
- Map WetterOnline condition codes to HA's fixed `condition` string set
  (`sunny`, `partlycloudy`, `rainy`, …). This mapping table is the single most
  error-prone part — build it explicitly and test it.

## 5. Testing (required for core)

- `pytest-homeassistant-custom-component`, aiming for **100% config-flow
  coverage** (Bronze quality scale requirement), including: manual happy path,
  invalid auth, cannot-connect, duplicate location abort, discovery pre-fill,
  reauth, and options.
- Mock the API with `aioresponses`; add fixtures for a representative
  forecast payload.
- Snapshot-test the weather entity and the condition-mapping table.

## 6. Distribution

Same two-phase path as `wohome`:
1. **HACS first** — separate GitHub repo (or a monorepo HACS supports via
   `content_in_root`/manifest per integration; simplest is a dedicated repo),
   own `hacs.json`, own CI (hassfest + HACS validate), releases by tag.
2. **Core later** — the weather integration is likely the *easier* first core
   candidate than `wohome`, because it has no unauthenticated-local-API question
   to defend; it just needs the API-key auth, tests, and the brands entry.

## 7. Open questions for the team

- Does our public API already expose per-location current + daily + hourly in
  one authenticated endpoint set, or does that need building?
- Can the account system mint **device-scoped, revocable** tokens for the
  `/weather-service` handoff, distinct from the master API key?
- What are the concrete rate limits per tier (drives the default poll interval)?
- Geocoding: do we expose a location search endpoint, or should the flow accept
  only coordinates in v1?
- Privacy: the config flow sends the user's coordinates to our servers. This
  must be stated in the documentation (German users especially will ask).

## 8. Explicitly out of scope

- **Custom weather-radar Lovelace card** — a separate frontend project,
  distributed through HACS's *frontend* category as its own repo. It consumes
  whatever entities/tile URLs exist and does not affect either integration.
  Note: any radar/tile imagery URLs it needs should be exposed by *this* weather
  integration, not by the station.

## 9. Implementation status: skeleton (as of this branch)

A working skeleton of this integration exists at
`custom_components/wetteronline/`. It implements the full structure described
above with the **HTTP layer stubbed** — no network requests are made yet, so it
loads end-to-end against placeholder data (the config flow completes and the
weather entity renders dummy values). This lets UI/card work and config-flow
tests proceed before the real API and token support ship.

Files:

| File               | Status                                                        |
| ------------------ | ------------------------------------------------------------- |
| `__init__.py`      | Complete — setup/unload, `runtime_data`, typed config entry   |
| `api.py`           | **Stub** — returns placeholder data, no I/O (see TODOs below)  |
| `config_flow.py`   | Complete — user, location, discovery+confirm, reauth, reconfigure, options |
| `coordinator.py`   | Complete — auth error → `ConfigEntryAuthFailed`, else `UpdateFailed` |
| `weather.py`       | Complete except the condition map (see TODOs below)           |
| `diagnostics.py`   | Complete — redacts API key and coordinates                    |
| `const.py`, `manifest.json`, `strings.json`, `translations/{en,de}.json` | Complete |

### Wiring to do once the API exists

All network wiring is marked with `# TODO(api)` comments:

- `api.py` → `async_validate_key()` — `GET /account`; raise `WetterOnlineAuthError`
  on 401, `WetterOnlineConnectionError` on network/5xx.
- `api.py` → `async_search_location(query)` — `GET /geocode?q=`.
- `api.py` → `async_get_weather(location)` — `GET /weather?lat=&lon=`.
- `weather.py` → `CONDITION_MAP` — complete the WetterOnline condition-code →
  HA `condition` mapping once the real code set is documented.
- `manifest.json` → `requirements` — add the pinned WetterOnline PyPI client
  once it is published (currently `[]`).

### Not yet done

- **Tests** — the Bronze-tier 100% config-flow coverage is not written yet.
- **Companion sensors** (UV, pollen, precipitation probability) — deferred to a
  later release as noted in §1.
- The station-side `GET /api/v1/weather-service` endpoint (§2b) and the
  discovery trigger in the `wohome` integration that calls it — the weather
  side (`async_step_integration_discovery`) is ready to receive the handoff,
  but nothing emits it yet.
