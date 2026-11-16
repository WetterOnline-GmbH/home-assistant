# WOHome - HA Integration

> **INTERNAL USE ONLY - NOT AVAILABLE FOR PUBLIC USE YET**

Custom integration for connecting WOHome stations locally to Home Assistant.

## Features

- Automatic detection of compatible stations via Zeroconf (`_woh4._tcp.local.`)
- Turn the screen on and off and display the current screen status
- Control display brightness and the device's automatic brightness setting
- View and update the device's display schedule rules
- Optional presence-based display automation using a blueprint
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
1. Search for "WetterOnline Home" in HACS and install the integration
1. Add the automatically detected WOHome under **Settings → Devices & Services**.
  - If you are on a different network add it manually **Settings → Devices & Services → Add Integration → WetterOnline Home**.

After setup, the dashboard can be customized via the `Dashboard` select entity in the configuration section of the respective device.

## Display and presence

These features require a WO Home app version that advertises brightness and display-rule control.
Older devices continue to expose the existing screen switch and sensors.
Reload the integration after updating the device so its new capabilities are detected.

The **Display brightness** slider sets a persistent manual brightness (6–100%) and disables
automatic brightness, including when an automation changes it. Use **Automatically adjust screen
brightness** to enable the light sensor again. Older app versions use a temporary override and
retain the **Restore device brightness** button. The screen switch respects active device schedule
rules when turning on; it cannot wake the device during scheduled standby. With no active rules,
the schedule permits the screen to be on.

The [presence blueprint](blueprints/automation/wohome/presence_display.yaml) can be imported
in **Settings → Automations & scenes → Blueprints → Import blueprint** using the GitHub URL
of that file. Create an automation and choose the presence entity, screen switch, brightness
slider and schedule binary sensor belonging to the same WO Home. Choose a brightness for
presence and either a dim level or standby for absence. A delay avoids reacting to brief
absences. Unknown or unavailable presence/schedule states do not trigger a screen change.
Device schedule rules take precedence; schedule status is refreshed before the automation
acts. The device independently checks the schedule before an HA-requested wake-up.

## Display schedule rules

The **Display schedule rules** sensor shows the number of rules and exposes the current
rules in its `rules` attribute. Rules remain stored and executed on WO Home. Administrators
can update them through **Developer tools → Actions → WO Home: Update display schedule rules**.
Select the integration entry, copy the current `rules` attribute to **Current rules**, and
enter the edited list in **New rules**. Each rule has `is_active`, `from`, `to`, and
`weekdays` (English weekday names from `Monday` through `Sunday`).

The update is rejected if the device's rules changed since they were copied; refresh the
sensor and try again. This avoids overwriting edits made on WO Home. Editing individual
rules directly in the HA UI is not yet supported; the action edits the complete list.

## Development

The integration communicates via the local WOHome API v1 on port `8080`. Before installation, you can verify the syntax and Home Assistant configuration as follows, for example:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
