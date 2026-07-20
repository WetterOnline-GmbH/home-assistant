# Implementation brief: WoHome station local API (Android app)

**Audience:** an engineer (or Claude) implementing the device side, working in
the WoHome Android app repository — a *different* codebase from the Home
Assistant integration. This document is self-contained: it states the exact
contract the Home Assistant integrations rely on. Implement to this contract
precisely; the field names, paths, and Zeroconf records are load-bearing.

## 1. What you are building

The WoHome station (an Android weather-station tablet) must expose a small
**local HTTP API** on the LAN so Home Assistant can:

1. Discover the station automatically (Zeroconf/mDNS).
2. Read the station's built-in sensors (temperature, humidity, ambient light).
3. Turn the screen on/off and read its current state.
4. Receive a Home Assistant dashboard URL to display.
5. *(New)* Optionally hand Home Assistant a WetterOnline API token and a default
   location, so the user gets weather in Home Assistant without typing an API
   key. **This endpoint hands over credentials only — it must not proxy or
   serve forecast data.**

Items 1–4 already have a working Home Assistant client; match their contract
exactly or you will break existing installs. Item 5 is new and is the main task.

## 2. Transport and framing

- Plain HTTP (not HTTPS) on the local network. Default port **8080**.
- All endpoints are under the base path **`/api/v1`**.
  Full URL shape: `http://<station-ip>:8080/api/v1/<endpoint>`.
- Request and response bodies are JSON. Responses should set
  `Content-Type: application/json` (the HA client tolerates a missing/odd
  content type, but set it correctly anyway).
- The API is currently **unauthenticated**. It must only be served on the local
  network interface, never exposed to the internet. (A future auth scheme can be
  added under a bumped `api_version`; do not add one unilaterally now — the HA
  client does not send credentials.)

## 3. Zeroconf / mDNS advertisement

The station must advertise itself via mDNS so Home Assistant discovers it.

- **Service type:** `_woh4._tcp.local.`
- **Port:** the HTTP API port (8080).
- **TXT records (properties)** — all keys lowercase. Home Assistant compares
  `model` and `manufacturer` case-insensitively and requires a stable `id`:

  | TXT key        | Value                        | Notes                                    |
  | -------------- | ---------------------------- | ---------------------------------------- |
  | `model`        | `WOH4`                       | Must match (case-insensitive)            |
  | `manufacturer` | `WetterOnline`               | Must match (case-insensitive)            |
  | `id`           | stable unique device id      | Used as the Home Assistant unique id     |

  The `id` must be **stable across reboots and network changes** (e.g. a
  hardware id or a persisted UUID). Home Assistant keys the device on it; if it
  changes, the device is re-added as a duplicate.

## 4. Existing endpoints (match exactly)

### `GET /api/v1/info`

Identity and capability probe. Called during discovery and setup.

```json
{
  "api_version": 1,
  "id": "a1b2c3d4",
  "name": "WetterOnline Home Wohnzimmer",
  "manufacturer": "WetterOnline",
  "model": "WOH4",
  "software_version": "1.4.2"
}
```

- `api_version` **must be the integer `1`**. Home Assistant refuses setup if it
  is anything else. Only bump it on a breaking change to this contract.
- `id` must equal the Zeroconf `id`.
- `name` is the user-facing device name shown in Home Assistant. `manufacturer`,
  `model`, `software_version` populate the HA device page.

### `GET /api/v1/state`

Current sensor readings and screen state. Polled every ~15 seconds.

```json
{
  "sensors": {
    "temperature_celsius": 21.4,
    "humidity_percent": 48,
    "illuminance_lux": 320
  },
  "display": {
    "is_on": true
  }
}
```

- Keys must be **exactly** `temperature_celsius`, `humidity_percent`,
  `illuminance_lux`, and `display.is_on`. Home Assistant reads these names
  directly; a missing key makes that sensor report "unknown" (acceptable), a
  renamed key breaks it.
- Numeric values are numbers, not strings. `is_on` is a JSON boolean.

### `PUT /api/v1/display`

Turn the screen on or off.

- Request body: `{ "is_on": true }` (or `false`).
- On success return HTTP 200. A JSON body is optional; Home Assistant does not
  require specific content, only a 2xx status. Reflect the new state in the next
  `GET /state`.

### `PUT /api/v1/dashboard`

Tell the station which Home Assistant dashboard URL to display.

- Request body: `{ "url": "http://homeassistant.local:8123/lovelace" }`.
- The station should load/display that URL. Return HTTP 200 on success.
- The URL is a full absolute Home Assistant URL computed by Home Assistant.

## 5. New endpoint: weather-service handoff

This is the credential handoff described in the architecture. It lets a station
owner add the separate **WetterOnline Weather** Home Assistant integration
without manually entering an API key.

### `GET /api/v1/weather-service`

**When the feature is enabled** (user turned it on in the station's developer /
Home Assistant settings, and the station has a usable WetterOnline account):

```json
{
  "api_key": "wo_live_9f8a...redacted",
  "location": {
    "id": "DE0001020",
    "lat": 50.11,
    "lon": 8.68,
    "label": "Frankfurt am Main"
  },
  "account_tier": "premium"
}
```

- `api_key` — a **device-scoped, revocable token**, *not* the user's master
  account key. See §6.
- `location` — the station's currently configured location. `id` is a stable
  WetterOnline location identifier; `lat`/`lon` are decimal degrees; `label` is
  a human-readable name. Home Assistant uses this only as a **default** — the
  user can change the location afterward, so it is fine if it differs from what
  they want.
- `account_tier` — a string (e.g. `basic`, `premium`) that lets Home Assistant
  pick a sensible default poll interval. Optional; omit if unknown.

**When the feature is disabled** (or no account is available): return HTTP
**404** (feature not offered) or **403** (present but not authorized). Return no
body, or a small `{ "error": "..." }`. Home Assistant treats any non-200 here as
"no handoff available" and silently skips it — so a disabled feature must not
produce errors in the Home Assistant log.

### Field contract summary (for §5)

| Field                | Type   | Required | Meaning                                  |
| -------------------- | ------ | -------- | ---------------------------------------- |
| `api_key`            | string | yes      | Device-scoped WetterOnline token         |
| `location.id`        | string | yes      | Stable WetterOnline location id          |
| `location.lat`       | number | yes      | Latitude, decimal degrees                |
| `location.lon`       | number | yes      | Longitude, decimal degrees               |
| `location.label`     | string | yes      | Human-readable location name             |
| `account_tier`       | string | no       | Account tier hint for poll interval      |

## 6. Token requirements (important)

The `api_key` returned by `/weather-service` must be a **device-scoped,
revocable token**, distinct from the user's master WetterOnline account key:

- It authenticates against the WetterOnline weather + account API from Home
  Assistant, but can be **revoked independently** (e.g. from the user's
  WetterOnline account, or when the tablet is reset) without rotating the master
  key.
- This limits blast radius if a tablet is lost or the LAN is compromised (the
  API is unauthenticated locally, so anyone on the LAN can read this endpoint
  while the feature is enabled — hence device scoping and revocability, and
  hence the feature being opt-in).
- The token should carry or map to a rate-limit tier so server-side throttling
  is predictable.

> **Dependency:** this requires the WetterOnline backend to support minting and
> revoking device-scoped tokens. That work is a prerequisite and is **not** part
> of the Android app; the app only fetches and serves whatever token the backend
> issues to it. If the backend cannot yet issue such a token, ship items 1–4 and
> leave `/weather-service` returning 404 until it can.

## 7. How Home Assistant consumes the handoff (context, do not implement)

For your understanding only — this is the Home Assistant side, already scaffolded
in the separate integration repo:

1. After the `wohome` device integration finishes setup, it calls
   `GET /api/v1/weather-service`.
2. On a 200, it triggers an `integration_discovery` flow for the `wetteronline`
   integration, passing `api_key`, `location`, and `account_tier`.
3. The user sees a confirm dialog ("Add WetterOnline Weather for
   Frankfurt am Main?") and confirms. A weather entity is created.
4. From then on, Home Assistant talks **directly** to the WetterOnline cloud
   with the token; the station is no longer involved in weather data.

Your job is only to make step 1 return correct data (or a clean 404 when
disabled) and to keep the token valid/revocable.

## 8. Acceptance checklist

- [ ] mDNS advertises `_woh4._tcp.local.` on the API port with TXT `model`,
      `manufacturer`, `id` (stable).
- [ ] `GET /api/v1/info` returns `api_version: 1` and a stable `id` matching mDNS.
- [ ] `GET /api/v1/state` returns the exact sensor/display key names in §4.
- [ ] `PUT /api/v1/display` toggles the screen and is reflected in `/state`.
- [ ] `PUT /api/v1/dashboard` loads the given URL.
- [ ] `GET /api/v1/weather-service` returns the §5 shape when enabled, and a
      bodyless 404/403 when disabled — never a 500 or a stack trace.
- [ ] The API binds to the LAN interface only, never the public internet.
- [ ] The weather-service token is device-scoped and revocable (backend
      dependency; coordinate before shipping item 5).

## 9. Out of scope for the Android app

- Serving or proxying forecast data (Home Assistant fetches it from the cloud
  directly).
- Any weather-radar imagery/tiles (handled by a future Home Assistant card +
  the cloud API, not the tablet).
- Authentication on the local API (deferred to a future `api_version`).
