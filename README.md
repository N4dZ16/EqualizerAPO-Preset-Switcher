# Equalizer APO Preset Switcher

A tiny local Windows app that switches [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) presets without opening `config.txt` by hand.

## Features

- Lists every `.txt` file in the Equalizer APO `config` folder (except `config.txt`) in a dropdown.
- Preamp slider (−20 to +20 dB) plus a precise text field. Values outside the range are rejected.
- **Apply** writes the chosen `Include:` and `Preamp:` lines into `config.txt`.
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

```
pip install pyinstaller
pyinstaller --onefile --windowed --name "EqAPO Preset Switcher" eqapo_preset_switcher.py
```

The exe appears in `dist/`. Add `--uac-admin` if you want it to always start with administrator rights.

## Administrator rights

`C:\Program Files\...` is often write-protected. If saving fails, the app offers to restart itself as administrator.

## How `config.txt` is edited

Only the first `Preamp:` line and the first `Include:` line are replaced (added if missing). All other lines, comments and line endings are left untouched.

```
Preamp: -6 dB
Include: Vocal Forward.txt
```

## License

MIT (add a `LICENSE` file when you publish).
