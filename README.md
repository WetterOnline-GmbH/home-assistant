# WOHome - HA Integration

> **INTERNAL USE ONLY - NOT AVAILABLE FOR PUBLIC USE YET**

Custom integration for connecting WOHome stations locally to Home Assistant.

## Features

- Automatic detection of compatible stations via Zeroconf (`_woh4._tcp.local.`)
- Turn the screen on and off and display the current screen status
- Control display brightness and the device's automatic brightness setting
- Provide temperature, humidity, and ambient brightness as sensors
- Select a Home Assistant dashboard for each station and send it to the station
- Show a camera stream in the station's native video dialog from an automation, preferring WebRTC with an HLS fallback
- Support for multiple stations within a single Home Assistant installation

## Requirements

- Home Assistant 2026.3 or newer for the existing station controls
- Home Assistant 2026.11.1 or newer for the camera action (earlier versions have not been tested)
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

## Camera dialog

Use **WetterOnline Home: Show camera** in an automation or under **Developer Tools → Actions**.
Select the station and a camera entity; no stream URL or camera credentials are required.
The station wakes up, displays the video without audio, and closes it after 30 seconds by default.
An incoming camera replaces the current video; repeated requests reset the display duration.
Closing the dialog returns to the previous screen and restores standby if the display was initially off.
The station starts connecting as soon as the command arrives and shows a loading screen until a video
frame has actually been rendered. No permanent camera preloading or extra snapshot requests are enabled.
The station releases its player when closed or backgrounded. A provider may retain a not-yet-connected
server peer until its ICE timeout; the action does not delete shared streams or interrupt other viewers.

```yaml
action: wohome.open_camera
data:
  device_id: YOUR_STATION_DEVICE_ID
  camera_entity_id: camera.front_door
  duration: 30
```

This requires a station app with the camera dialog API. With WebRTC-capable station apps,
the action prefers Home Assistant's WebRTC camera support, including native camera integrations
and providers such as go2rtc. HLS is requested only if WebRTC is unavailable or fails to connect.
Older station apps continue to use HLS. WebRTC-only cameras work if negotiation and media connectivity succeed;
they cannot fall back to HLS unless the camera also supports it.

WebRTC signaling uses a signed, expiring Home Assistant URL scoped to the selected camera.
The station receives no general Home Assistant credentials. Treat this URL as a secret.
HLS playback, including the fallback, uses a Home Assistant stream token that is not tied to
the signed URL's expiry. Anyone who obtains that token can access the stream while it remains
active. Keep stream URLs private and use this prototype only on a trusted network.
WebRTC additionally requires reachable ICE candidates: a working dashboard or signaling connection alone
does not prove that video packets can reach the station. Separate networks may require configured
go2rtc candidates, firewall rules, or a TURN server. The native player uses ICE servers supplied by HA.
It does not bypass certificate validation or promise support for every camera codec.
Configure Home Assistant's local URL under **Settings → System → Network** so the station can
reach it, including any HLS playlists and segments. The existing dashboard login does not authenticate
the native player; the action resolves a Home Assistant stream URL for each request instead.
Stream URLs must not be stored in automations or logs. Only use this unauthenticated device API
on a trusted network.

## Display brightness

These features require a WO Home app version that advertises brightness control.
Older devices continue to expose the existing screen switch and sensors.
Reload the integration after updating the device so its new capabilities are detected.

The **Display brightness** slider sets a persistent manual brightness (0–100%) and disables
automatic brightness, including when an automation changes it. 0% corresponds to the minimum
device value of 1. Use **Automatically adjust screen brightness** to enable the light sensor again.

## Development

The integration communicates via the local WOHome API v1 on port `8080`. Before installation, you can verify the syntax and Home Assistant configuration as follows, for example:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
