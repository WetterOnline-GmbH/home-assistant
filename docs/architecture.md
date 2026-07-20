# Architecture overview

## Abstract

The WetterOnline Home Assistant offering is built from **two independent
integrations** plus an optional frontend card, rather than one combined
component. This split follows Home Assistant's core modeling rule: a *device*
integration represents a physical device on the local network, while *weather
for a location* is a cloud service.

- **`wohome`** is a local-polling **device** integration. It talks to a
  WoHome weather-station tablet over a local HTTP API (discovered via Zeroconf)
  and exposes the station's own hardware: indoor temperature, humidity and
  ambient-light sensors, a screen on/off switch, and a selector that pushes a
  Home Assistant dashboard URL to the tablet.

- **`wetteronline`** is a cloud-polling **service** integration. It fetches
  WetterOnline forecast data for a chosen location directly from the
  WetterOnline servers using an API key, and exposes a standard Home Assistant
  `weather` entity. It works for everyone, with or without a station.

The two are connected only by an optional **discovery handoff**: a station that
has the feature enabled can hand the `wetteronline` integration a
device-scoped API token and a default location, so station owners get a
near-zero-setup weather entity. Crucially, the forecast data does **not** flow
through the tablet — the tablet only bootstraps credentials. Home Assistant
becomes the source of truth for the configured location, which avoids the
problems of multiple stations, differing station locations, and users without a
station.

A future weather-radar Lovelace card is a separate frontend project that
consumes whatever entities and tile URLs the `wetteronline` integration exposes;
it does not affect either integration.

## System context

```mermaid
flowchart TB
    user([Home Assistant user])

    subgraph cloud["WetterOnline cloud"]
        api[Weather + account API<br/>API key / device token]
    end

    subgraph lan["Local network"]
        station[WoHome station<br/>Android tablet<br/>local HTTP API :8080]
    end

    subgraph ha["Home Assistant"]
        wohome[wohome integration<br/>local_poll · device]
        weather[wetteronline integration<br/>cloud_poll · service]
        card[Weather radar card<br/>optional frontend]
    end

    user --> ha
    station -->|pulls forecast| api
    wohome -->|Zeroconf + HTTP| station
    weather -->|HTTPS + API key| api
    wohome -.->|discovery handoff:<br/>token + location| weather
    card -.->|reads entities| weather
```

## Component view of the integrations

```mermaid
flowchart LR
    subgraph wohome["wohome (device)"]
        w_flow[config_flow<br/>zeroconf + manual]
        w_coord[DataUpdateCoordinator<br/>polls /state every 15s]
        w_api[WoHomeApi<br/>local HTTP client]
        w_sensor[sensors:<br/>temp / humidity / lux]
        w_switch[switch: screen]
        w_select[select: dashboard]
        w_flow --> w_coord
        w_coord --> w_api
        w_coord --> w_sensor
        w_coord --> w_switch
        w_coord --> w_select
    end

    subgraph weather["wetteronline (service)"]
        m_flow[config_flow<br/>API key + location<br/>+ discovery + reauth]
        m_coord[DataUpdateCoordinator<br/>polls weather per tier]
        m_api[WetterOnlineApiClient<br/>cloud HTTP client]
        m_weather[weather entity<br/>daily + hourly forecast]
        m_flow --> m_coord
        m_coord --> m_api
        m_coord --> m_weather
    end

    w_api -->|local| station[(WoHome station)]
    m_api -->|HTTPS| wocloud[(WetterOnline cloud)]
    w_coord -.->|hands off token + location| m_flow
```

## Discovery handoff sequence

How a station owner gets a weather entity with no manual key entry:

```mermaid
sequenceDiagram
    participant S as WoHome station
    participant W as wohome integration
    participant M as wetteronline integration
    participant U as User

    Note over W: station already set up in HA
    W->>S: GET /api/v1/weather-service
    alt feature enabled on station
        S-->>W: 200 { api_key, location, account_tier }
        W->>M: async_init(integration_discovery,<br/>token + location)
        M->>U: "Add WetterOnline Weather for <location>?"
        U-->>M: Confirm
        M->>M: create entry (location = unique_id)
        Note over M: HA now owns the location -<br/>user can reconfigure it
    else feature disabled
        S-->>W: 404 / 403
        Note over W: skip silently — no weather entry
    end
```

## Key decisions

- **Two integrations, not one.** Keeps each aligned with its Home Assistant
  archetype (device vs. service) and lets non-station users consume weather.
- **Tablet bootstraps credentials, never carries data.** Removes the
  multi-station, wrong-location, and no-station failure modes.
- **Location lives in Home Assistant.** The station's location is only a
  default; the user can override it and HA remains authoritative.
- **Device-scoped, revocable token** for the handoff, distinct from the raw
  account API key, so a lost tablet can be revoked without rotating the key.
