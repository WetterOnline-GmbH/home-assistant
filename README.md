# weather & radar home — Home Assistant integration

Connect weather & radar home (wetteronline home) stations locally to Home Assistant.
This guide covers API v2. See [GitHub Releases](https://github.com/WetterOnline-GmbH/home-assistant/releases)
for available stable and pre-release versions.

## Features

- Automatic detection of compatible stations via Zeroconf (`_woh4._tcp.local.`)
- Turn the screen on and off and display the current screen status
- Control display brightness and the device's automatic brightness setting
- Provide temperature, humidity, and ambient brightness as sensors
- Select a Home Assistant dashboard for each station and send it to the station
- Show a camera stream in the station's native video dialog from an automation, preferring WebRTC with an HLS fallback
- Support for multiple stations within a single Home Assistant installation

## Requirements

- Home Assistant 2026.3 or newer for station controls. Use 2026.11.1 or newer for the camera action;
  earlier versions have not been tested with it.
- A station app that supports API v2, with the Home Assistant feature enabled in the station's developer settings.

The station API requires pairing and HTTPS with certificate pinning. Never forward port `8080` to the Internet.
After updating both the station app and the integration from API v1, use **Reconfigure** on the existing
entry to pair it without removing its entities or automations.

## Installation

1. On Home Assistant 2026.11 or newer, open **Settings → Marketplace → Add from link**. Connect GitHub if prompted.
   On older versions, use [HACS → Custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/).
2. Add `https://github.com/WetterOnline-GmbH/home-assistant` as an **Integration** and install it.
   To install a beta in the Marketplace, [enable pre-releases](https://www.home-assistant.io/integrations/marketplace/#keeping-installations-up-to-date) for the repository.
3. Restart Home Assistant. Under **Settings → Devices & services**, select the discovered **wetteronline home**
   station. If it is not discovered, select **Add integration → wetteronline home** and enter its address.
4. Compare the pairing code in Home Assistant with the one on the station. If they match, confirm on the
   station first, then continue in Home Assistant.

After setup, the dashboard can be customized via the `Dashboard` select entity in the configuration section of the respective device.
Choose **No dashboard** there to hide the dashboard button on the station; select a dashboard again to show it.

## Camera dialog

Use **wetteronline home: Show camera (select station)** in an automation or under **Developer Tools → Actions**.
Select the station and a camera entity; no stream URL or camera credentials are required.
In the automation editor, **By target → device** also offers **Show camera**.
It targets the station's screen switch and can target several stations; the original
`wohome.open_camera` action and its `device_id` field remain supported.
The screen switch must be enabled and visible for device or area target expansion.
Stations without camera support reject the action when it runs.
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
the signed URL's expiry. The device API now transfers these URLs over HTTPS, but the subsequent
video and dashboard requests still use the configured Home Assistant URL. If that URL is HTTP,
anyone who can observe that network traffic may obtain the stream token or dashboard login.
Use HTTPS for Home Assistant if the home network is not trusted.
WebRTC additionally requires reachable ICE candidates: a working dashboard or signaling connection alone
does not prove that video packets can reach the station. Separate networks may require configured
go2rtc candidates, firewall rules, or a TURN server. The native player uses ICE servers supplied by HA.
It does not bypass certificate validation or promise support for every camera codec.
Configure Home Assistant's local URL under **Settings → System → Network** so the station can
reach it, including any HLS playlists and segments. The existing dashboard login does not authenticate
the native player; the action resolves a Home Assistant stream URL for each request instead.
Stream URLs must not be stored in automations or logs.

## Display brightness

These features require a WO Home app version that advertises brightness control.
Older devices continue to expose the existing screen switch and sensors.
Reload the integration after updating the device so its new capabilities are detected.

The **Display brightness** slider sets a persistent manual brightness (0–100%) and disables
automatic brightness, including when an automation changes it. 0% corresponds to the minimum
device value of 1. Use **Automatically adjust screen brightness** to enable the light sensor again.

## Development

The integration communicates via the local WOHome API v2 over HTTPS on port `8080`. Before installation, you can verify the syntax and Home Assistant configuration as follows, for example:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
