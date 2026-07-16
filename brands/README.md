# Brand assets for the WetterOnline Home integration

These files are **not** used by the integration at runtime. Home Assistant
serves integration icons and logos from the central
[home-assistant/brands](https://github.com/home-assistant/brands) repository.

## What to submit

The directory layout under `custom_integrations/wohome/` in this folder mirrors
exactly what the brands repository expects. To publish the icon/logo:

1. Fork [home-assistant/brands](https://github.com/home-assistant/brands).
2. Copy `custom_integrations/wohome/` into the same path in that fork.
3. Open a pull request.

Once merged, the icon appears automatically in the config-flow, device page,
and HACS listing — no change to this repository is required.

When the integration is later accepted into Home Assistant core, the same
assets move from `custom_integrations/wohome/` to `core_integrations/wohome/`
in the brands repository.

## Asset requirements (already satisfied here)

| File          | Size    | Notes                                |
| ------------- | ------- | ------------------------------------ |
| `icon.png`    | 256×256 | Square, transparent background       |
| `icon@2x.png` | 512×512 | hDPI variant of the icon             |
| `logo.png`    | 256×256 | Square logo (may be wider if desired)|
| `logo@2x.png` | 512×512 | hDPI variant of the logo             |

All four are trimmed of surrounding whitespace and use a transparent
background, per the brands repository guidelines.
