# Equalizer APO Preset Switcher

A tiny local Windows app that switches [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) presets without opening `config.txt` by hand.

## Features

- Lists every `.txt` file in the Equalizer APO `config` folder (except `config.txt`) in a dropdown.
- Preamp slider (−20 to +20 dB) plus a precise text field. Values outside the range are rejected.
- **Apply** writes the chosen preset name and preamp into `config.txt`. It never switches the preset on or off: an active `Include:` line stays active, a commented one stays commented.
- **Reset** puts the selection and preamp back to what `config.txt` currently has.
- **Turn preset OFF / ON** comments or uncomments the `Include:` line (`# Include: Vocal Forward.txt`). The `Preamp:` line is not touched.
- Color-coded status banner:
  - 🟢 green: selected preset and preamp are the ones in `config.txt`
  - 🟠 orange: not applied yet (different preset, or same preset with a different preamp)
  - 🔴 red: invalid preamp value
- The dropdown marks the active preset with ●. The app picks up outside changes to `config.txt` automatically.
- Finds the config folder automatically (registry, then `Program Files`), otherwise asks for it. The choice is saved in `%APPDATA%\EqualizerAPOPresetSwitcher\settings.json`; use **Change folder…** to switch.

## Run

Requires Python 3.8+ (with Tk, included in the standard Windows installer). No other packages.

```
python eqapo_preset_switcher.py
```

## Build a standalone .exe

Keep the window icon in an `assets` folder next to the script (any `.ico`, or `.png`, works).

```
pip install pyinstaller
pyinstaller --onefile --windowed --name "EqAPO Preset Switcher" --icon "assets\eqapo-switcher-no-bg-ico.ico" --add-data "assets;assets" eqapo_preset_switcher.py
```

Adjust the icon file name if yours differs. `--icon` sets the .exe's file icon, `--add-data` bundles the assets so the window icon works in the built app.

The exe appears in `dist/`. Add `--uac-admin` if you want it to always start with administrator rights.

## Administrator rights

`C:\Program Files\...` is often write-protected. If saving fails, the app offers to restart itself as administrator.

## How `config.txt` is edited

Only the first `Preamp:` line and the first `Include:` line are replaced (added if missing). All other lines, comments and line endings are left untouched. Turning the preset OFF comments every active `Include:` line; turning it ON uncomments the one that was switched off (the app remembers which). Applying a preset while it is OFF changes the name inside the `# Include:` line and keeps it commented, so there is still only one Include line. If the file has no Include line at all, Apply adds an active one.

```
Preamp: -6 dB
Include: Vocal Forward.txt
```

## License

MIT
