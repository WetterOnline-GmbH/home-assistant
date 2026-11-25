# weather & radar home - Home Assistant Integration

> Early access: the latest stable release is 0.3.0; the API v2 integration is available as the
> opt-in [0.4.0-beta.3 pre-release](https://github.com/WetterOnline-GmbH/home-assistant/releases/tag/0.4.0-beta.3).

Custom integration for connecting weather & radar home devices (wetteronline home) locally to Home Assistant.

## Features

- Automatic detection of compatible stations via Zeroconf (`_woh4._tcp.local.`)
- Turn the screen on and off and display the current screen status
- Control display brightness and the device's automatic brightness setting
- Provide temperature, humidity, and ambient brightness as sensors
- Select a Home Assistant dashboard for each station and send it to the station
- In the 0.4.0 beta: show a Home Assistant camera in the station's video dialog from an automation (WebRTC, with HLS fallback)
- Support for multiple stations within a single Home Assistant installation

## Requirements

- Home Assistant 2026.3 or newer for station controls; 2026.11.1 or newer for the beta camera action (earlier versions have not been tested)
- Home Assistant feature enabled in the station's developer settings
- For the 0.4.0 beta, a station app with the paired API v2; camera playback requires the wetteronline home app 2026.23.4 or newer (currently on the Dev channel)

The stable 0.3.0 integration uses the unauthenticated HTTP API v1 and should only be used
on a trusted network. The 0.4.0 beta pairs with the station and uses HTTPS with certificate
pinning for the device API. Never expose port `8080` to the Internet.

Existing entries can be paired via **Reconfigure** after updating both the station and the
integration; do not delete an existing entry just to update it. Compare the code shown in
Home Assistant with the code on the station and confirm on the station only if they match.

## Installation

On Home Assistant 2026.11 or newer, add this repository through the
[Marketplace](https://www.home-assistant.io/integrations/marketplace/#custom-repositories).
It is **not yet listed in the catalog**, so searching the catalog alone will not find it.

1. Go to **Settings → Marketplace → Add from link**. Connect GitHub if prompted.
2. Enter `https://github.com/WetterOnline-GmbH/home-assistant` and select **Add** (type **Integration** if prompted).
3. Open the repository in the Marketplace and install it. Stable releases are offered by default.
   For the 0.4.0 beta, enable the disabled-by-default **Pre-release** entity on the repository's
   device under **Settings → Devices & services → Marketplace**, turn on its switch, and install
   the offered beta version.
4. Restart Home Assistant after updating the integration. Add the automatically discovered
   **wetteronline home** under **Settings → Devices & services**. If discovery does not work
   across networks, use **Add integration → wetteronline home** and enter the station's address.

After setup, the dashboard can be customized via the `Dashboard` select entity in the configuration section of the respective device.
Choose **No dashboard** to hide the dashboard button on the station; select a dashboard again to show it.

## Camera dialog (0.4.0 beta)

Use **wetteronline home: Show camera (select station)** in an automation or under
**Developer Tools → Actions**. Select the station and a camera entity; no stream URL or camera
credentials are required. In the automation editor, **By target → device** also offers
**Show camera**. It targets the station's screen switch and can target several stations; the
original `wohome.open_camera` action and its `device_id` field remain supported. The screen
switch must be enabled and visible for device or area target expansion. Stations without camera
support reject the action when it runs.

The station wakes up, displays the video without audio, and closes it after 30 seconds by default.
An incoming camera replaces the current video; repeated requests reset the display duration.
Closing the dialog returns to the previous screen and restores standby if the display was initially off.

```yaml
action: wohome.open_camera
data:
  device_id: YOUR_STATION_DEVICE_ID
  camera_entity_id: camera.front_door
  duration: 30
```

With WebRTC-capable station apps, the action prefers Home Assistant's WebRTC camera support,
including native camera integrations and providers such as go2rtc. HLS is requested if WebRTC
is unavailable or fails to connect; older station apps use HLS. WebRTC-only cameras cannot fall
back unless they also support HLS. WebRTC needs reachable ICE candidates: a working dashboard
or signaling connection does not prove that video packets can reach the station.

Set Home Assistant's local URL under **Settings → System → Network** so the station can reach it,
including HLS playlists and segments. The device API uses HTTPS, but camera and dashboard
requests use the configured Home Assistant URL. If it is HTTP, anyone who can observe the
network traffic may obtain the stream token or dashboard login; use HTTPS outside a trusted
private network. Do not store stream URLs in automations or logs.

## Display brightness

These features require a station app version that advertises brightness control.
Older devices continue to expose the existing screen switch and sensors.
Reload the integration after updating the device so its new capabilities are detected.

The **Display brightness** slider sets a persistent manual brightness (0–100%) and disables
automatic brightness, including when an automation changes it. 0% corresponds to the minimum
device value of 1. Use **Automatically adjust screen brightness** to enable the light sensor again.

## Development

The integration communicates with the station on port `8080` (HTTP API v1 in 0.3.0; paired HTTPS API v2 in the 0.4.0 beta). To check the syntax and Home Assistant configuration:

```shell
python3 -m compileall -q custom_components/wohome
ha core check
```
