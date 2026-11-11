#!/usr/bin/env python3
"""
Equalizer APO Preset Switcher
=============================

A tiny, dependency-free (standard library only) Windows app that switches
Equalizer APO presets by editing the "Preamp:" and "Include:" lines of
config.txt for you.

Run:    python eqapo_preset_switcher.py
Build:  pyinstaller --onefile --windowed --name "EqAPO Preset Switcher" eqapo_preset_switcher.py
"""

import codecs
import ctypes
import json
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

APP_TITLE = "Equalizer APO Preset Switcher"
CONFIG_NAME = "config.txt"
PREAMP_MIN, PREAMP_MAX = -20.0, 20.0
POLL_MS = 2000

SETTINGS_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "EqualizerAPOPresetSwitcher"
)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

FONT = "Segoe UI"
GREEN, ORANGE, RED, GREY = "#2e7d32", "#c77700", "#c62828", "#546e7a"

PREAMP_RE = re.compile(r"^\s*Preamp\s*:\s*([-+]?\d+(?:\.\d+)?)\s*dB\b.*$", re.I)
INCLUDE_RE = re.compile(r"^\s*Include\s*:\s*(.+?)\s*$", re.I)
COMMENTED_INCLUDE_RE = re.compile(r"^\s*#+\s*Include\s*:\s*(.+?)\s*$", re.I)

# Window icon: looked up in an "assets" folder next to the script (or one level up).
ICON_NAMES = ("eqapo-switcher-no-bg-ico", "eqapo-switcher-no-bg")


# --------------------------------------------------------------------------
# Settings & folder detection
# --------------------------------------------------------------------------
def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def is_valid_folder(path):
    return bool(path) and os.path.isfile(os.path.join(path, CONFIG_NAME))


def candidate_folders():
    """Possible Equalizer APO config folders, most reliable first."""
    cands = []
    if sys.platform == "win32":
        try:
            import winreg

            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\EqualizerAPO",
                        0,
                        winreg.KEY_READ | view,
                    ) as key:
                        install_path = winreg.QueryValueEx(key, "InstallPath")[0]
                        cands.append(os.path.join(install_path, "config"))
                except OSError:
                    pass
        except ImportError:
            pass
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "EqualizerAPO", "config"))
    cands.append(r"C:\Program Files\EqualizerAPO\config")
    return cands


def detect_folder():
    for path in candidate_folders():
        if is_valid_folder(path):
            return path
    return None


# --------------------------------------------------------------------------
# config.txt handling
# --------------------------------------------------------------------------
def decode_text(raw):
    """Return (text, encoding) so we can write the file back the way we found it."""
    if raw.startswith(codecs.BOM_UTF8):
        return raw[3:].decode("utf-8"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "cp1252"


def encode_text(text, encoding):
    try:
        return text.encode(encoding)
    except UnicodeEncodeError:
        return text.encode("utf-8")


def fmt_preamp(value):
    value = round(value, 1) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"{value:g}"


def fmt_field(value):
    return f"{round(value, 1) + 0.0:.1f}"


def _clean(value):
    return value.strip().strip('"')


def parse_config(text):
    """Return (preamp, include, commented_include).

    `include` is the first active Include line; `commented_include` the first
    "# Include: ..." line. Each is None if absent.
    """
    preamp = include = commented = None
    for line in text.splitlines():
        m = PREAMP_RE.match(line)
        if m and preamp is None:
            preamp = float(m.group(1))
            continue
        m = INCLUDE_RE.match(line)
        if m:
            if include is None:
                include = _clean(m.group(1))
            continue
        m = COMMENTED_INCLUDE_RE.match(line)
        if m and commented is None:
            commented = _clean(m.group(1))
    return preamp, include, commented


def update_config(text, preamp, include, remembered=None):
    """Set the Preamp value and the preset file name, WITHOUT changing on/off state.

    - An active "Include:" line gets the new name and stays active.
    - If the preset is off, the "# Include:" line gets the new name and stays commented
      (the one matching `remembered` if there are several, else the first).
    - If there is no Include line at all, an active one is added.
    Everything else in the file is left untouched.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    preamp_line = f"Preamp: {fmt_preamp(preamp)} dB"
    lines = text.splitlines()

    commented_idx = None
    if not any(INCLUDE_RE.match(l) for l in lines):
        first = None
        for i, l in enumerate(lines):
            m = COMMENTED_INCLUDE_RE.match(l)
            if not m:
                continue
            if first is None:
                first = i
            if remembered and _clean(m.group(1)).lower() == remembered.lower():
                commented_idx = i
                break
        if commented_idx is None:
            commented_idx = first

    out, done_p, done_i = [], False, False
    for i, line in enumerate(lines):
        if not done_p and PREAMP_RE.match(line):
            out.append(preamp_line)
            done_p = True
        elif not done_i and INCLUDE_RE.match(line):
            out.append(f"Include: {include}")
            done_i = True
        elif not done_i and i == commented_idx:
            lead = line[: len(line) - len(line.lstrip())]
            out.append(f"{lead}# Include: {include}")
            done_i = True
        else:
            out.append(line)
    if not done_p:
        out.insert(0, preamp_line)
    if not done_i:
        out.append(f"Include: {include}")
    return newline.join(out) + newline


def disable_include(text):
    """Comment out the active Include line(s): "Include: X" -> "# Include: X".

    Returns (new_text, name_of_first_include) or None if there was nothing to do.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    out, first = [], None
    for line in text.splitlines():
        m = INCLUDE_RE.match(line)
        if m:
            if first is None:
                first = _clean(m.group(1))
            lead = line[: len(line) - len(line.lstrip())]
            out.append(f"{lead}# {line.strip()}")
        else:
            out.append(line)
    if first is None:
        return None
    return newline.join(out) + newline, first


def enable_include(text, prefer=None):
    """Uncomment one "# Include: X" line: the one for `prefer` if present, else the first."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    first = chosen = None
    for i, line in enumerate(lines):
        m = COMMENTED_INCLUDE_RE.match(line)
        if not m:
            continue
        if first is None:
            first = i
        if prefer and _clean(m.group(1)).lower() == prefer.lower():
            chosen = i
            break
    idx = chosen if chosen is not None else first
    if idx is None:
        return None
    line = lines[idx]
    lead = line[: len(line) - len(line.lstrip())]
    lines[idx] = lead + re.sub(r"^\s*#+\s*", "", line)
    return newline.join(lines) + newline


def list_presets(folder):
    names = []
    for name in os.listdir(folder):
        low = name.lower()
        if low.endswith(".txt") and low != CONFIG_NAME and os.path.isfile(os.path.join(folder, name)):
            names.append(name)
    return sorted(names, key=str.lower)


def same_preset(include, name, folder):
    """True if config.txt's Include value points at preset file `name`."""
    if not include or not name:
        return False
    target = include if os.path.isabs(include) else os.path.join(folder, include)
    mine = os.path.join(folder, name)
    return os.path.normcase(os.path.normpath(target)) == os.path.normcase(os.path.normpath(mine))


def parse_preamp_input(text):
    """Return (value, error). Exactly one of them is None."""
    s = re.sub(r"\s*db$", "", text.strip().replace(",", "."), flags=re.I)
    range_msg = f"Preamp must be between {PREAMP_MIN:+g} and {PREAMP_MAX:+g} dB."
    if not s:
        return None, "Enter a number. " + range_msg
    try:
        v = float(s)
    except ValueError:
        return None, "Not a number. " + range_msg
    if not math.isfinite(v):
        return None, "Not a number. " + range_msg
    if v < PREAMP_MIN or v > PREAMP_MAX:
        return None, range_msg
    return v, None


# --------------------------------------------------------------------------
# Admin helpers (config.txt in Program Files is often write-protected)
# --------------------------------------------------------------------------
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    params = " ".join(f'"{a}"' for a in args)
    try:
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1) > 32
    except Exception:
        return False


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
class MarqueeLabel(tk.Frame):
    """Fixed-size, single-line label. Text that doesn't fit scrolls in a loop."""

    STEP_MS = 30
    PAUSE_MS = 1500

    def __init__(self, master, width, font, fg, bg, padx=0, pady=0, step=1, gap=40):
        super().__init__(master, bg=bg)
        self._font = tkfont.Font(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        line_h = self._font.metrics("linespace") + 2
        self._avail = width - 2 * padx
        self._step, self._gap, self._fg = step, gap, fg
        self._y = line_h // 2
        self._canvas = tk.Canvas(self, width=self._avail, height=line_h, bg=bg, highlightthickness=0, bd=0)
        self._canvas.pack(padx=padx, pady=pady)
        self.config(width=width, height=line_h + 2 * pady)
        self.pack_propagate(False)
        self._text, self._items, self._offset, self._tw, self._job = "", [], 0, 0, None

    def set(self, text=None, fg=None, bg=None):
        if bg is not None:
            self.config(bg=bg)
            self._canvas.config(bg=bg)
        if fg is not None:
            self._fg = fg
            for item in self._items:
                self._canvas.itemconfig(item, fill=fg)
        if text is not None and text != self._text:
            self._text = text
            self._restart()

    def _restart(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        c = self._canvas
        c.delete("all")
        self._offset = 0
        self._tw = self._font.measure(self._text)
        self._items = [c.create_text(0, self._y, text=self._text, anchor="w", font=self._font, fill=self._fg)]
        if self._tw > self._avail:  # too long: second copy makes the loop seamless
            self._items.append(
                c.create_text(self._tw + self._gap, self._y, text=self._text, anchor="w",
                              font=self._font, fill=self._fg)
            )
            self._job = self.after(self.PAUSE_MS, self._tick)

    def _tick(self):
        loop = self._tw + self._gap
        self._offset += self._step
        pause = self._offset >= loop
        if pause:
            self._offset = 0
        self._canvas.coords(self._items[0], -self._offset, self._y)
        self._canvas.coords(self._items[1], loop - self._offset, self._y)
        self._job = self.after(self.PAUSE_MS if pause else self.STEP_MS, self._tick)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.scale = self.winfo_fpixels("1i") / 96.0
        self._set_icon()

        self.settings = load_settings()
        self.folder = None
        self.presets = []
        self.active_include = None
        self.commented_include = None
        self.active_preamp = None
        self.last_valid = 0.0
        self._mtime = None
        self._flash_id = None

        self.preamp_var = tk.StringVar(value="0.0")
        self.slider_var = tk.DoubleVar(value=0.0)
        self.error_var = tk.StringVar(value="")

        self._build_ui()
        self.preamp_var.trace_add("write", self._on_entry_change)

        self._init_folder()
        self.reload(initial=True)
        self.after(POLL_MS, self._poll)

    # ---- window icon -----------------------------------------------------
    def _set_icon(self):
        roots = []
        if getattr(sys, "frozen", False):
            roots.append(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
        here = os.path.dirname(os.path.abspath(__file__))
        roots += [here, os.path.dirname(here)]
        for root in roots:
            assets = os.path.join(root, "assets")
            if not os.path.isdir(assets):
                continue
            candidates = [n + ext for n in ICON_NAMES for ext in (".ico", ".png", "")]
            others = sorted(os.listdir(assets), key=lambda n: (not n.lower().endswith(".ico"), n.lower()))
            candidates += [n for n in others if n.lower().endswith((".ico", ".png"))]
            for name in candidates:
                path = os.path.join(assets, name)
                if os.path.isfile(path) and self._try_icon(path):
                    return

    def _try_icon(self, path):
        try:
            with open(path, "rb") as f:
                head = f.read(4)
            if head == b"\x00\x00\x01\x00":  # .ico
                self.iconbitmap(path)
            else:  # PNG/GIF
                self._icon_img = tk.PhotoImage(file=path)
                self.iconphoto(True, self._icon_img)
            return True
        except (OSError, tk.TclError):
            return False

    # ---- layout ----------------------------------------------------------
    def px(self, n):
        return int(round(n * self.scale))

    def _build_ui(self):
        style = ttk.Style(self)
        for theme in ("vista", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Apply.TButton", font=(FONT, 11, "bold"), padding=8)
        style.configure("Toggle.TButton", font=(FONT, 10), padding=5)
        bg = style.lookup("TFrame", "background") or self.cget("bg")
        win_w = self.px(460)
        cw = win_w - 2 * self.px(18)  # content width
        self.configure(bg=bg)

        root = ttk.Frame(self, padding=self.px(18))
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Equalizer APO", font=(FONT, 16, "bold")).pack(anchor="w")
        ttk.Label(root, text="Preset switcher", foreground="#666", font=(FONT, 10)).pack(
            anchor="w", pady=(0, 12)
        )

        self.banner = MarqueeLabel(
            root, cw, (FONT, 11, "bold"), "white", GREY,
            padx=self.px(12), pady=self.px(10), step=max(1, self.px(1)),
        )
        self.banner.pack()
        self.config_info = MarqueeLabel(root, cw, (FONT, 9), "#666666", bg, step=max(1, self.px(1)))
        self.config_info.pack(pady=(4, 14))

        # Preset selector
        ttk.Label(root, text="Preset", font=(FONT, 10, "bold")).pack(anchor="w")
        row = ttk.Frame(root)
        row.pack(fill="x", pady=(4, 14))
        self.combo = ttk.Combobox(row, state="readonly", font=(FONT, 10))
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        ttk.Button(row, text="\u27f3", width=3, command=self.refresh).pack(side="left", padx=(6, 0))

        # Preamp
        head = ttk.Frame(root)
        head.pack(fill="x")
        ttk.Label(head, text="Preamp", font=(FONT, 10, "bold")).pack(side="left")
        box = ttk.Frame(head)
        box.pack(side="right")
        self.entry = tk.Entry(
            box, textvariable=self.preamp_var, width=7, justify="right",
            font=(FONT, 10), relief="solid", bd=1, highlightthickness=0,
        )
        self.entry.pack(side="left")
        ttk.Label(box, text=" dB").pack(side="left")
        self.entry.bind("<Return>", self._commit_entry)
        self.entry.bind("<FocusOut>", self._commit_entry)

        self.slider = ttk.Scale(
            root, from_=PREAMP_MIN, to=PREAMP_MAX, orient="horizontal",
            variable=self.slider_var, command=self._on_slider,
        )
        self.slider.pack(fill="x", pady=(8, 0))
        scale = ttk.Frame(root)
        scale.pack(fill="x")
        ttk.Label(scale, text=f"{PREAMP_MIN:+g} dB", font=(FONT, 8), foreground="#666").pack(side="left")
        ttk.Label(scale, text=f"{PREAMP_MAX:+g} dB", font=(FONT, 8), foreground="#666").pack(side="right")
        ttk.Label(scale, text="0", font=(FONT, 8), foreground="#666").pack(expand=True)

        self.error_label = tk.Label(
            root, textvariable=self.error_var, fg=RED, font=(FONT, 9),
            anchor="w", justify="left", wraplength=cw, height=2, bg=bg,
        )
        self.error_label.pack(fill="x", pady=(2, 4))

        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x", pady=(0, 8))
        self.reset_btn = ttk.Button(btn_row, text="Reset", style="Apply.TButton", command=self.reset, width=8)
        self.reset_btn.pack(side="left", padx=(0, 8))
        self.apply_btn = ttk.Button(btn_row, text="Apply preset", style="Apply.TButton", command=self.apply)
        self.apply_btn.pack(side="left", fill="x", expand=True)

        self.toggle_btn = ttk.Button(root, text="Turn preset OFF", style="Toggle.TButton", command=self.toggle)
        self.toggle_btn.pack(fill="x", pady=(0, 14))

        foot = ttk.Frame(root)
        foot.pack(fill="x")
        btn = ttk.Button(foot, text="Change folder\u2026", command=self.choose_folder)
        btn.pack(side="right")
        self.update_idletasks()
        self.folder_label = MarqueeLabel(
            foot, cw - btn.winfo_reqwidth() - self.px(10), (FONT, 8), "#666666", bg,
            step=max(1, self.px(1)),
        )
        self.folder_label.pack(side="left")

        # Fixed window size: nothing in the UI changes size when text changes.
        self.update_idletasks()
        self.geometry(f"{win_w}x{self.winfo_reqheight()}")
        self.resizable(False, False)

    # ---- folder handling -------------------------------------------------
    def _init_folder(self):
        saved = self.settings.get("config_folder")
        if is_valid_folder(saved):
            self.folder = saved
        else:
            self.folder = detect_folder()
            if self.folder:
                self._remember_folder()
        if not self.folder:
            self.after(300, self._prompt_for_folder)
        self._update_folder_label()

    def _remember_folder(self):
        self.settings["config_folder"] = self.folder
        save_settings(self.settings)

    def _update_folder_label(self):
        self.folder_label.set(self.folder or "No folder selected")

    def _prompt_for_folder(self):
        messagebox.showinfo(
            APP_TITLE,
            "Couldn't find Equalizer APO automatically.\n\n"
            "Please select its \"config\" folder (the one containing config.txt).",
        )
        self.choose_folder()

    def choose_folder(self):
        start = self.folder or os.environ.get("ProgramFiles", "C:\\")
        path = filedialog.askdirectory(title="Select the Equalizer APO config folder", initialdir=start)
        if not path:
            return
        path = os.path.normpath(path)
        if not is_valid_folder(path):
            messagebox.showerror(APP_TITLE, f"That folder doesn't contain {CONFIG_NAME}.")
            return
        self.folder = path
        self._remember_folder()
        self._update_folder_label()
        self.reload(initial=True)

    # ---- loading / refreshing --------------------------------------------
    def selected_preset(self):
        idx = self.combo.current()
        return self.presets[idx] if 0 <= idx < len(self.presets) else None

    def refresh(self):
        self.reload()

    def reload(self, initial=False):
        keep = None if initial else self.selected_preset()
        self.presets, self.active_preamp, self.active_include = [], None, None
        self.commented_include = None
        if self.folder:
            try:
                self.presets = list_presets(self.folder)
            except OSError as exc:
                messagebox.showerror(APP_TITLE, f"Couldn't read the folder:\n{exc}")
            cfg = os.path.join(self.folder, CONFIG_NAME)
            try:
                with open(cfg, "rb") as f:
                    text, _ = decode_text(f.read())
                self.active_preamp, self.active_include, self.commented_include = parse_config(text)
                self._mtime = os.path.getmtime(cfg)
            except OSError:
                self._mtime = None
        self._rebuild_combo(keep)
        if initial and self.active_preamp is not None:
            self.preamp_var.set(fmt_field(self.active_preamp))
        self.update_status()

    def _current_include(self):
        """The preset named in config.txt: the active Include, else the commented one (off)."""
        return self.active_include if self.active_include is not None else self.commented_include

    def _rebuild_combo(self, prefer):
        mark = "\u25cf " if self.active_include is not None else "\u25cb "  # filled = on, hollow = off
        cur = self._current_include()
        self.combo["values"] = [
            (mark if same_preset(cur, n, self.folder) else "    ") + n for n in self.presets
        ]
        target = prefer if prefer in self.presets else None
        if target is None:
            target = next((n for n in self.presets if same_preset(cur, n, self.folder)), None)
        if target is None and self.presets:
            target = self.presets[0]
        if target is not None:
            self.combo.current(self.presets.index(target))
        else:
            self.combo.set("")

    def _poll(self):
        """Pick up outside changes (e.g. config.txt edited elsewhere, presets added)."""
        if self.folder:
            try:
                mtime = os.path.getmtime(os.path.join(self.folder, CONFIG_NAME))
                if mtime != self._mtime or list_presets(self.folder) != self.presets:
                    self.reload()
            except OSError:
                pass
        self.after(POLL_MS, self._poll)

    # ---- events ----------------------------------------------------------
    def _on_preset_selected(self, _event=None):
        self.combo.selection_clear()
        self.update_status()

    def _on_slider(self, value):
        self.preamp_var.set(fmt_field(round(float(value) * 2) / 2))  # 0.5 dB steps

    def _on_entry_change(self, *_):
        value, err = parse_preamp_input(self.preamp_var.get())
        if err is None:
            self.last_valid = value
            self.slider_var.set(value)
            self.error_var.set("")
            self.entry.config(bg="white")
        else:
            self.error_var.set(err)
            self.entry.config(bg="#fde8e8")
        self.update_status()

    def _commit_entry(self, _event=None):
        value, err = parse_preamp_input(self.preamp_var.get())
        if err is None:
            self.preamp_var.set(fmt_field(value))
            return
        # Reject: restore the last valid value and say why for a few seconds.
        self.preamp_var.set(fmt_field(self.last_valid))
        self.error_var.set("Rejected. " + err)
        if self._flash_id:
            self.after_cancel(self._flash_id)
        self._flash_id = self.after(4000, lambda: self.error_var.set(""))

    # ---- status & apply --------------------------------------------------
    def update_status(self):
        sel = self.selected_preset()
        value, err = parse_preamp_input(self.preamp_var.get())

        info_p = "not set" if self.active_preamp is None else f"{fmt_preamp(self.active_preamp)} dB"
        off = self.active_include is None and self.commented_include is not None
        info_i = self.active_include or (f"OFF (# {self.commented_include})" if off else "none")
        self.config_info.set(f"config.txt \u2192 Preamp: {info_p}  \u00b7  Include: {info_i}")

        if not self.folder:
            text, color, can_apply = "Select your Equalizer APO config folder to get started.", GREY, False
        elif sel is None:
            text, color, can_apply = f"No preset files found in this folder.", GREY, False
        elif err is not None:
            text, color, can_apply = "Invalid preamp \u2013 fix the value to apply.", RED, False
        else:
            preset_ok = same_preset(self._current_include(), sel, self.folder)
            preamp_ok = self.active_preamp is not None and abs(value - self.active_preamp) < 0.05
            if off and preset_ok and preamp_ok:
                text, color, can_apply = "Preset OFF \u2013 this preset is set in config.txt but switched off.", GREY, False
            elif off:
                text, color, can_apply = f"Preset OFF \u2013 changes not applied yet (config.txt: {info_i}).", ORANGE, True
            elif preset_ok and preamp_ok:
                text, color, can_apply = "\u2714  Active \u2013 this preset and preamp are applied.", GREEN, False
            elif preset_ok:
                text, color, can_apply = (
                    f"Preset is active, but the preamp differs ({info_p} in config.txt).",
                    ORANGE, True,
                )
            else:
                text, color, can_apply = f"Not active \u2013 currently active: {info_i}", ORANGE, True

        self.banner.set(text, bg=color)
        self.apply_btn.state(["!disabled"] if can_apply else ["disabled"])

        if self.folder and (self.active_include is not None or off):
            self.toggle_btn.config(text="Turn preset ON" if off else "Turn preset OFF")
            self.toggle_btn.state(["!disabled"])
        else:
            self.toggle_btn.config(text="Turn preset OFF")
            self.toggle_btn.state(["disabled"])

        # Reset is useful whenever the UI differs from what's in config.txt.
        active_name = self._active_preset_name()
        differs = (active_name is not None and sel != active_name) or (
            self.active_preamp is not None and (err is not None or abs(value - self.active_preamp) >= 0.05)
        )
        self.reset_btn.state(["!disabled"] if (self.folder and differs) else ["disabled"])

    def _active_preset_name(self):
        cur = self._current_include()
        return next((n for n in self.presets if same_preset(cur, n, self.folder)), None)

    def reset(self):
        """Put the selection and preamp back to what config.txt currently has."""
        name = self._active_preset_name()
        if name is not None:
            self.combo.current(self.presets.index(name))
        if self.active_preamp is not None:
            self.preamp_var.set(fmt_field(self.active_preamp))
        self.error_var.set("")
        self.update_status()

    def _modify_config(self, transform):
        """Read config.txt, apply transform(text) -> new text (or None), write it back."""
        cfg = os.path.join(self.folder, CONFIG_NAME)
        try:
            with open(cfg, "rb") as f:
                text, enc = decode_text(f.read())
            new_text = transform(text)
            if new_text is None:
                return False
            data = encode_text(new_text, enc)
            with open(cfg, "wb") as f:
                f.write(data)
        except PermissionError:
            self._handle_permission_error()
            return False
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Couldn't write {CONFIG_NAME}:\n{exc}")
            return False
        return True

    def apply(self):
        sel = self.selected_preset()
        value, err = parse_preamp_input(self.preamp_var.get())
        if not self.folder or sel is None or err is not None:
            return
        remembered = self.settings.get("last_disabled_include")
        was_off = {}

        def change(text):
            _, include, commented = parse_config(text)
            was_off["v"] = include is None and commented is not None
            return update_config(text, value, sel, remembered)

        if self._modify_config(change):
            if was_off.get("v"):  # still off: remember which commented line is ours
                self.settings["last_disabled_include"] = sel
                save_settings(self.settings)
            self.reload()

    def toggle(self):
        """Comment / uncomment the Include line. The Preamp line is left as is."""
        if not self.folder:
            return
        if self.active_include is not None:
            disabled = {}

            def turn_off(text):
                result = disable_include(text)
                if result is None:
                    return None
                disabled["name"] = result[1]
                return result[0]

            if self._modify_config(turn_off) and disabled:
                self.settings["last_disabled_include"] = disabled["name"]
                save_settings(self.settings)
        elif self.commented_include is not None:
            prefer = self.settings.get("last_disabled_include")
            self._modify_config(lambda text: enable_include(text, prefer))
        self.reload()

    def _handle_permission_error(self):
        if sys.platform == "win32" and not is_admin():
            if messagebox.askyesno(
                APP_TITLE,
                f"Windows won't let this app modify {CONFIG_NAME} (the folder is protected).\n\n"
                "Restart the app as administrator?",
            ):
                if relaunch_as_admin():
                    self.destroy()
                else:
                    messagebox.showerror(APP_TITLE, "Couldn't restart as administrator.")
        else:
            messagebox.showerror(APP_TITLE, f"Permission denied while writing {CONFIG_NAME}.")


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
