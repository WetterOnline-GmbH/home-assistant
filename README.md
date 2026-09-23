# WOHome - HA Integration

> **INTERNAL USE ONLY - NOT AVAILABLE FOR PUBLIC USE YET**

Custom integration for connecting WOHome stations locally to Home Assistant.

## Features

- Automatic detection of compatible stations via Zeroconf (`_woh4._tcp.local.`)
- Turn the screen on and off and display the current screen status
- Provide temperature, humidity, and ambient brightness as sensors
- Select a Home Assistant dashboard for each station and send it to the station
- Support for multiple stations within a single Home Assistant installation

## Requirements

- Home Assistant 2026.3 or newer
- Home Assistant feature enabled in the WOHome developer settings

The local device API currently does not use authentication and should only be used on a trusted network.

## Installation

1. Install the repo via HACS:
   - Click the 3 dots in the top right corner.
   - Select “Custom repositories”
   - Add the URL to the repository. (https://github.com/WetterOnline-GmbH/home-assistant)
   - Select “integration” as the type.
   - Click the “ADD” button.
1. Add the automatically detected WOHome under **Settings → Devices & Services**.

After setup, the dashboard can be customized via the `Dashboard` select entity in the configuration section of the respective device.

## Development

The integration communicates via the local WOHome API v1 on port `8080`. Before installation, you can verify the syntax and Home Assistant configuration as follows, for example:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
