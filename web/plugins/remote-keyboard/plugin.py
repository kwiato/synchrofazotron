"""Remote Keyboard plugin — the device as a USB keyboard for the PC.

Lifted from pimote (github.com/kwiato/pimote): with the dwc2 overlay in
peripheral mode and the HID gadget from install.sh, the Pi shows up on the
PC's USB port as a plain keyboard, /dev/hidg0. Every 8-byte report written
there is a key press (modifiers, reserved, up to six key codes); an all-zero
report releases everything. Codes are USB HID usages, layout-independent — the
layout Windows has active decides which (modifier, code) pair makes which
character, hence the layout setting.

State: plugins-data/remote-keyboard/config.json = {"layout": "pl"|"us"}.
API (under /api/p/remote-keyboard):
  GET  /state  -> {status: ready|no_pc|reboot|no_gadget|sandbox, layout, udc}
  POST /type   {text}          -> {ok, message, typed, skipped}
  POST /key    {key, mods: []} -> {ok, message}
  POST /config {layout}        -> {ok, message, layout}
"""
import glob
import json
import os
import select
import threading
import time

DEV = "/dev/hidg0"
UDC_STATE = "/sys/class/udc/*/state"
BOOT_CFGS = ("/boot/firmware/config.txt", "/boot/config.txt")
OVERLAY = "dtoverlay=dwc2,dr_mode=peripheral"
MAX_TEXT = 2000
KEY_DELAY = 0.006     # press / release pause while typing text
WRITE_WAIT = 0.5      # seconds to wait for the PC to take a report

MOD = {"ctrl": 0x01, "shift": 0x02, "alt": 0x04, "win": 0x08, "gui": 0x08,
       "altgr": 0x40, "ralt": 0x40}   # AltGr = right Alt (Polish characters)

KEYS = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08, "f": 0x09, "g": 0x0a,
    "h": 0x0b, "i": 0x0c, "j": 0x0d, "k": 0x0e, "l": 0x0f, "m": 0x10, "n": 0x11,
    "o": 0x12, "p": 0x13, "q": 0x14, "r": 0x15, "s": 0x16, "t": 0x17, "u": 0x18,
    "v": 0x19, "w": 0x1a, "x": 0x1b, "y": 0x1c, "z": 0x1d,
    "1": 0x1e, "2": 0x1f, "3": 0x20, "4": 0x21, "5": 0x22, "6": 0x23, "7": 0x24,
    "8": 0x25, "9": 0x26, "0": 0x27,
    "enter": 0x28, "esc": 0x29, "backspace": 0x2a, "tab": 0x2b, "space": 0x2c,
    "f1": 0x3a, "f2": 0x3b, "f3": 0x3c, "f4": 0x3d, "f5": 0x3e, "f6": 0x3f,
    "f7": 0x40, "f8": 0x41, "f9": 0x42, "f10": 0x43, "f11": 0x44, "f12": 0x45,
    "delete": 0x4c, "home": 0x4a, "end": 0x4d, "pageup": 0x4b, "pagedown": 0x4e,
    "up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4f,
}

SHIFT = MOD["shift"]
ALTGR = MOD["altgr"]


def _base_chars():
    """char -> (modifiers, code) for plain US ASCII. Shared by "us" and "pl"
    (Polish Programmers keeps the US positions and adds AltGr diacritics)."""
    chars = {}
    for c in "abcdefghijklmnopqrstuvwxyz":
        chars[c] = (0, KEYS[c])
        chars[c.upper()] = (SHIFT, KEYS[c])
    for d in "1234567890":
        chars[d] = (0, KEYS[d])
    for sym, d in zip("!@#$%^&*()", "1234567890"):
        chars[sym] = (SHIFT, KEYS[d])
    chars.update({
        " ": (0, 0x2c), "-": (0, 0x2d), "_": (SHIFT, 0x2d),
        "=": (0, 0x2e), "+": (SHIFT, 0x2e), "[": (0, 0x2f), "{": (SHIFT, 0x2f),
        "]": (0, 0x30), "}": (SHIFT, 0x30), "\\": (0, 0x31), "|": (SHIFT, 0x31),
        ";": (0, 0x33), ":": (SHIFT, 0x33), "'": (0, 0x34), "\"": (SHIFT, 0x34),
        "`": (0, 0x35), "~": (SHIFT, 0x35), ",": (0, 0x36), "<": (SHIFT, 0x36),
        ".": (0, 0x37), ">": (SHIFT, 0x37), "/": (0, 0x38), "?": (SHIFT, 0x38),
        "\t": (0, 0x2b), "\n": (0, 0x28),
    })
    return chars


def _with_polish(chars):
    """Polish diacritics as AltGr + base letter (Polish "Programmers")."""
    for pl, base in {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
                     "ó": "o", "ś": "s", "ź": "x", "ż": "z"}.items():
        chars[pl] = (ALTGR, KEYS[base])
        chars[pl.upper()] = (ALTGR | SHIFT, KEYS[base])
    return chars


LAYOUTS = {"us": _base_chars, "pl": lambda: _with_polish(_base_chars())}
DEFAULT_LAYOUT = "pl"

_ctx = None
_cfg_path = ""
_lock = threading.Lock()   # one writer at a time, reports must not interleave


def setup(ctx):
    global _ctx, _cfg_path
    _ctx = ctx
    _cfg_path = os.path.join(ctx["data_dir"], "config.json")


# --- config -----------------------------------------------------------------

def _config():
    try:
        with open(_cfg_path, encoding="utf-8") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        c = {}
    layout = str(c.get("layout", DEFAULT_LAYOUT))
    return {"layout": layout if layout in LAYOUTS else DEFAULT_LAYOUT}


def _save(cfg):
    os.makedirs(os.path.dirname(_cfg_path), exist_ok=True)
    with open(_cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)


# --- gadget state -------------------------------------------------------------

def _udc_state():
    """'configured' once the PC has enumerated the gadget, 'not attached' /
    'powered' / … otherwise, '' when there is no UDC at all (overlay not
    active)."""
    for p in glob.glob(UDC_STATE):
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            pass
    return ""


def _overlay_present():
    for p in BOOT_CFGS:
        try:
            with open(p, encoding="utf-8") as fh:
                if any(line.strip() == OVERLAY for line in fh):
                    return True
        except OSError:
            continue
    return False


def _status():
    if _ctx["dev"]:
        return "sandbox"
    if os.path.exists(DEV):
        return "ready" if _udc_state() == "configured" else "no_pc"
    return "reboot" if _overlay_present() else "no_gadget"


# --- HID writes -------------------------------------------------------------------

class _NoHost(Exception):
    """The PC is not taking reports (cable, PC off, not enumerated)."""


def _open():
    # Non-blocking + select: a blocking write on an un-polled endpoint would
    # hang the panel's request thread for good.
    return os.open(DEV, os.O_RDWR | os.O_NONBLOCK)


def _write(fd, report):
    _, ready, _ = select.select([], [fd], [], WRITE_WAIT)
    if not ready:
        raise _NoHost()
    try:
        os.write(fd, report)
    except BlockingIOError as e:
        raise _NoHost() from e


def _press(fd, mod, code):
    _write(fd, bytes([mod, 0, code, 0, 0, 0, 0, 0]))
    time.sleep(KEY_DELAY)
    _write(fd, bytes(8))
    time.sleep(KEY_DELAY)


def _type_text(text, chars):
    """Returns (typed, skipped). Characters the layout cannot produce are
    skipped, never raised — like pimote."""
    typed = skipped = 0
    with _lock:
        fd = _open()
        try:
            for ch in text:
                if ch == "\r":
                    continue
                pair = chars.get(ch)
                if pair is None:
                    skipped += 1
                    continue
                _press(fd, *pair)
                typed += 1
        finally:
            os.close(fd)
    return typed, skipped


def _send_key(key, mods):
    mod = 0
    for m in mods:
        mod |= MOD[m]
    with _lock:
        fd = _open()
        try:
            _press(fd, mod, KEYS[key])
        finally:
            os.close(fd)


def _guarded(fn):
    """Run a HID action, turning the usual failures into {ok: False} answers."""
    if _ctx["dev"]:
        return {"ok": False, "message": "sandbox"}
    st = _status()
    if st in ("reboot", "no_gadget"):
        return {"ok": False, "message": st}
    try:
        return fn()
    except _NoHost:
        return {"ok": False, "message": "no_pc"}
    except OSError as e:
        _ctx["log"](f"hid write failed: {e}")
        return {"ok": False, "message": "write_fail", "detail": str(e)}


# --- routing ----------------------------------------------------------------------

def handle(method, path, body, query):
    cfg = _config()
    if method == "GET" and path == "/state":
        return {"status": _status(), "udc": _udc_state(), **cfg}

    if method == "POST" and path == "/type":
        text = body.get("text", "")
        if not isinstance(text, str) or not text:
            return {"ok": False, "message": "empty"}
        if len(text) > MAX_TEXT:
            return {"ok": False, "message": "too_long"}
        chars = LAYOUTS[cfg["layout"]]()

        def go():
            typed, skipped = _type_text(text, chars)
            _ctx["log"](f"typed {typed} chars, skipped {skipped}")
            return {"ok": True, "message": "typed", "typed": typed, "skipped": skipped}
        return _guarded(go)

    if method == "POST" and path == "/key":
        key = str(body.get("key", "")).lower()
        mods = body.get("mods") or []
        if key not in KEYS or not isinstance(mods, list) \
                or any(not isinstance(m, str) or m.lower() not in MOD for m in mods):
            return {"ok": False, "message": "bad_key"}
        mods = [m.lower() for m in mods]

        def go():
            _send_key(key, mods)
            return {"ok": True, "message": "sent"}
        return _guarded(go)

    if method == "POST" and path == "/config":
        layout = str(body.get("layout", "")).lower()
        if layout not in LAYOUTS:
            return {"ok": False, "message": "bad_layout"}
        cfg = {"layout": layout}
        _save(cfg)
        return {"ok": True, "message": "saved", **cfg}
    return None
