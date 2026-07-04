#!/usr/bin/env python3
"""
Synchrofazotron control panel — lightweight microservice (stdlib only).

Serves a mobile-friendly HTML page with:
  * an "Enable Bluetooth pairing" button (makes the adapter discoverable/
    pairable for a limited window; a separate persistent bt-agent service
    auto-accepts pairing so the headless Pi never has to confirm anything),
  * instructions for what and how to play on this device.

No external dependencies — runs on a clean DietPi / Raspberry Pi OS.
Listens on 0.0.0.0:8787 by default (reachable via Tailscale and LAN).
"""

import glob
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Configuration (tweak to taste; everything can be overridden via env)
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PISTREAM_PANEL_PORT", "8787"))
BIND = os.environ.get("PISTREAM_PANEL_BIND", "0.0.0.0")

_HOSTNAME = socket.gethostname() or "Synchrofazotron"
DEVICE_NAME = os.environ.get("PISTREAM_NAME", _HOSTNAME)   # BT / AirPlay name
LMS_PORT = 9000                    # Lyrion Music Server web UI port
SQUEEZELITE_PLAYER = os.environ.get("PISTREAM_LMS_PLAYER", _HOSTNAME)
PAIR_WINDOW_SEC = 180             # how long the Pi stays visible while pairing
SHOW_SPOTIFY = os.environ.get("PISTREAM_SPOTIFY", "0") == "1"  # raspotify not installed
WIFI_IFACE = os.environ.get("PISTREAM_WIFI_IFACE", "wlan0")
# Auto-pause: when a new source starts playing, pause the previous one.
# Essential on a hardware DAC (single substream — sources cannot mix there).
AUTOPAUSE = os.environ.get("PISTREAM_AUTOPAUSE", "1") == "1"

# ---------------------------------------------------------------------------
# Language (UI translations). Default from env, runtime choice persisted to a
# file next to the script so it survives panel updates (install.sh only
# replaces the .py file).
# ---------------------------------------------------------------------------
LANGS = ("en", "pl")
LANG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
_lang = os.environ.get("PISTREAM_LANG", "en")
try:
    _saved = open(LANG_FILE, encoding="utf-8").read().strip()
    if _saved in LANGS:
        _lang = _saved
except OSError:
    pass
if _lang not in LANGS:
    _lang = "en"


def _lang_set(lang):
    global _lang
    if lang not in LANGS:
        return False
    _lang = lang
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as fh:
            fh.write(lang + "\n")
    except OSError:
        pass  # non-fatal: language still switches until restart
    return True


# All user-visible strings. Keys are referenced from templates as {{T:key}}
# and from Python via T("key"). Keep strings free of single quotes and
# backslashes — some are embedded inside single-quoted JS literals.
STR = {
    "en": {
        "title_panel": "control panel",
        "title_settings": "settings",
        "sub_panel": "Audio player control panel",
        "settings_link_title": "Settings",
        "now_playing": "🎚️ Now playing",
        "warn_multi": "⚠️ Multiple sources are playing at once — the first one owns the DAC, the rest play into the void. Stop the ones you do not need.",
        "sources_note": "Starting a new source automatically pauses the previous one (exception: Spotify — pause it in its own app).",
        "bt_head": "📶 Bluetooth",
        "bt_intro": "Tap to make the device visible and ready to pair for <b>{{PAIR_WIN}} seconds</b>. Then on your phone: Bluetooth → select <b>{{DEVICE}}</b>.",
        "bt_button": "🔵 Enable Bluetooth pairing",
        "bt_status": "BT status:",
        "bt_after": "Once paired you can play from <b>any app</b> on your phone (YouTube Music, podcasts, anything) — the audio goes to {{DEVICE}}.",
        "spotify_head": "🟢 Spotify",
        "spotify_1": "Open the <b>Spotify</b> app on your phone/PC.",
        "spotify_2": "Tap the devices icon (Spotify Connect) and pick <b>{{DEVICE}}</b>.",
        "spotify_note": "No pairing needed — works over the network.",
        "airplay_head": "🍎 AirPlay",
        "airplay_1": "On iPhone/iPad/Mac open Control Center or the AirPlay icon in your music app.",
        "airplay_2": "Pick <b>{{DEVICE}}</b> as the speaker.",
        "lms_head": "🎧 TIDAL / radio / library (Lyrion Music Server)",
        "lms_1": "Install the <b>Squeezer</b> app (Android) or <b>iPeng</b> (iOS) — that is the main remote.",
        "lms_2": "Pick the <b>{{PLAYER}}</b> player and play TIDAL, internet radio, playlists.",
        "lms_web": "Or from a browser:",
        "lms_web2": "(Material Skin).",
        "audio_note_head": "ℹ️ A note about audio",
        "audio_note": "Audio goes out through the <b>DAC</b> (BossDAC). A playing source owns the DAC exclusively — when a new source starts, the previous one is paused automatically (Bluetooth may take a few seconds to take over; Spotify cannot be paused remotely). If something refuses to play, check above what else is playing.",
        "players_label": "Players:",
        # main page JS
        "js_pairing": "pairing: ",
        "js_ready": "ready",
        "js_off": "off",
        "js_connected": "connected: ",
        "js_silence": "Silence — nothing is playing.",
        "js_ctrl_hint": "control from the source app",
        "js_pair_active_pre": "✅ Pairing active — look for \"{{DEVICE}}\" (",
        "js_pair_active_suf": "s)",
        # source states (sent via /api/status)
        "state_playing": "playing",
        "state_paused": "paused",
        "state_idle": "idle",
        "state_connected": "connected",
        # settings page
        "settings_head": "⚙️ Settings",
        "back_to_panel": "← panel",
        "wifi_now_head": "📡 Wi-Fi — current connection",
        "wifi_saved_head": "💾 Saved networks",
        "wifi_saved_note": "The Pi automatically joins the first available network from this list (DietPi stores up to 5). Perfect for home + a second location.",
        "wifi_add_head": "➕ Add a network",
        "wifi_add_note": "Type it in by hand (networks out of range work too — SSID must match exactly!) or pick one from a scan.",
        "wifi_ssid_ph": "Network name (SSID)",
        "wifi_key_ph": "Password (empty = open network)",
        "wifi_save_btn": "Save network",
        "wifi_scan_btn": "🔍 Scan for networks",
        "viz_head": "📊 Visualizer (HDMI)",
        "viz_note": "Bar style on the monitor. Changing it restarts the visualizer (music keeps playing).",
        "lang_head": "🌐 Language",
        "lang_note": "Panel language. The choice is saved on the device.",
        "how_head": "ℹ️ How it works",
        "how_note": "Networks go into the DietPi database (the same one <code>dietpi-config</code> uses) and the Wi-Fi configuration is reloaded on the fly — no reboot. Removing the network you are currently connected through is blocked so you cannot lock yourself out.",
        # settings JS
        "js_wifi_connected": "connected",
        "js_wifi_none": "not connected",
        "js_lan_ip": "LAN IP: ",
        "js_ts_ip": "Tailscale: ",
        "js_no_saved": "No saved networks.",
        "js_slot": "slot ",
        "js_remove": "remove",
        "js_rm_pre": "Remove network \"",
        "js_rm_suf": "\"?",
        "js_saving": "Saving…",
        "js_error": "Error",
        "js_conn_error": "Connection error.",
        "js_scanning": "🔍 Scanning… (a few seconds)",
        "js_scan_none": "Nothing found (the radio can be busy — try again).",
        "js_scan_fail": "Scan failed — try again.",
        "js_viz_stop": "⏻ Stop visualizer",
        "js_viz_start": "⏻ Start visualizer",
        # server messages
        "wifi_bad_ssid": "Invalid SSID.",
        "wifi_bad_key": "A WPA password must be 8–63 characters (empty = open network).",
        "wifi_no_slot": "No free slot — DietPi stores up to {n} networks. Remove one first.",
        "wifi_saved_msg": "Saved „{ssid}” (slot {slot}).",
        "wifi_reload_warn": " Note: the wpa_supplicant reload did not confirm — the network will work after a reboot at the latest.",
        "wifi_empty_slot": "Empty slot.",
        "wifi_rm_current": "You are connected through this network right now — refusing to remove it remotely.",
        "wifi_removed": "Removed „{ssid}”.",
        "viz_unknown": "Unknown preset.",
        "viz_not_installed": "The visualizer is not installed.",
        "viz_preset_set": "Preset „{label}” applied.",
        "viz_stopped": "Visualizer stopped (until reboot / manual start).",
        "viz_started": "Visualizer started.",
        "lang_set": "Language switched to English.",
        # visualizer preset labels
        "preset_classic": "Classic",
        "preset_dense": "Dense",
        "preset_waves": "Waves",
        "preset_massive": "Massive",
    },
    "pl": {
        "title_panel": "panel",
        "title_settings": "ustawienia",
        "sub_panel": "Panel sterowania odtwarzaczem audio",
        "settings_link_title": "Ustawienia",
        "now_playing": "🎚️ Teraz gra",
        "warn_multi": "⚠️ Kilka źródeł gra jednocześnie — pierwsze zajmuje DAC, reszta gra w próżnię. Zatrzymaj niepotrzebne.",
        "sources_note": "Start nowego źródła automatycznie pauzuje poprzednie (wyjątek: Spotify — pauzuj w jego apce).",
        "bt_head": "📶 Bluetooth",
        "bt_intro": "Kliknij, żeby urządzenie stało się widoczne i gotowe do sparowania przez <b>{{PAIR_WIN}} sekund</b>. Potem w telefonie: Bluetooth → wybierz <b>{{DEVICE}}</b>.",
        "bt_button": "🔵 Włącz parowanie Bluetooth",
        "bt_status": "Status BT:",
        "bt_after": "Po sparowaniu możesz grać z <b>dowolnej apki</b> na telefonie (YouTube Music, podcasty, cokolwiek) — dźwięk poleci na {{DEVICE}}.",
        "spotify_head": "🟢 Spotify",
        "spotify_1": "Otwórz apkę <b>Spotify</b> na telefonie/PC.",
        "spotify_2": "Dotknij ikony urządzeń (Spotify Connect) i wybierz <b>{{DEVICE}}</b>.",
        "spotify_note": "Nie trzeba nic parować — działa po sieci.",
        "airplay_head": "🍎 AirPlay",
        "airplay_1": "Na iPhone/iPad/Mac otwórz Centrum sterowania lub ikonę AirPlay w apce muzycznej.",
        "airplay_2": "Wybierz <b>{{DEVICE}}</b> jako głośnik.",
        "lms_head": "🎧 TIDAL / radio / biblioteka (Lyrion Music Server)",
        "lms_1": "Zainstaluj apkę <b>Squeezer</b> (Android) lub <b>iPeng</b> (iOS) — to główny pilot.",
        "lms_2": "Wybierz odtwarzacz <b>{{PLAYER}}</b> i graj TIDAL, radio internetowe, playlisty.",
        "lms_web": "Albo z przeglądarki:",
        "lms_web2": "(Material Skin).",
        "audio_note_head": "ℹ️ Uwaga o dźwięku",
        "audio_note": "Dźwięk wychodzi przez <b>DAC</b> (BossDAC). Grające źródło zajmuje DAC na wyłączność — gdy startuje nowe źródło, poprzednie jest pauzowane automatycznie (przejęcie przez Bluetooth może potrwać kilka sekund; Spotify nie da się spauzować zdalnie). Jeśli coś nie chce zagrać, sprawdź wyżej, co jeszcze gra.",
        "players_label": "Odtwarzacze:",
        "js_pairing": "parowanie: ",
        "js_ready": "gotowy",
        "js_off": "wyłączony",
        "js_connected": "połączone: ",
        "js_silence": "Cisza — nic nie gra.",
        "js_ctrl_hint": "steruj z apki źródła",
        "js_pair_active_pre": "✅ Parowanie aktywne — szukaj \"{{DEVICE}}\" (",
        "js_pair_active_suf": "s)",
        "state_playing": "gra",
        "state_paused": "pauza",
        "state_idle": "cisza",
        "state_connected": "połączony",
        "settings_head": "⚙️ Ustawienia",
        "back_to_panel": "← panel",
        "wifi_now_head": "📡 Wi-Fi — bieżące połączenie",
        "wifi_saved_head": "💾 Zapisane sieci",
        "wifi_saved_note": "Pi łączy się automatycznie z pierwszą dostępną z tej listy (DietPi mieści maks. 5). Idealne na sieć domową + drugą lokalizację.",
        "wifi_add_head": "➕ Dodaj sieć",
        "wifi_add_note": "Wpisz ręcznie (sieci spoza zasięgu też można — SSID co do znaku!) albo wybierz ze skanu.",
        "wifi_ssid_ph": "Nazwa sieci (SSID)",
        "wifi_key_ph": "Hasło (puste = sieć otwarta)",
        "wifi_save_btn": "Zapisz sieć",
        "wifi_scan_btn": "🔍 Skanuj otoczenie",
        "viz_head": "📊 Wizualizer (HDMI)",
        "viz_note": "Styl słupków na monitorze. Zmiana restartuje wizualizer (muzyka gra dalej).",
        "lang_head": "🌐 Język",
        "lang_note": "Język panelu. Wybór zapisuje się na urządzeniu.",
        "how_head": "ℹ️ Jak to działa",
        "how_note": "Sieci trafiają do bazy DietPi (tej samej, którą widzi <code>dietpi-config</code>), a konfiguracja Wi-Fi jest przeładowywana w locie — bez restartu. Usunięcie sieci, przez którą aktualnie jesteś połączony, jest zablokowane, żeby nie odciąć sobie dostępu.",
        "js_wifi_connected": "połączony",
        "js_wifi_none": "brak połączenia",
        "js_lan_ip": "IP lokalne: ",
        "js_ts_ip": "Tailscale: ",
        "js_no_saved": "Brak zapisanych sieci.",
        "js_slot": "slot ",
        "js_remove": "usuń",
        "js_rm_pre": "Usunąć sieć „",
        "js_rm_suf": "”?",
        "js_saving": "Zapisuję…",
        "js_error": "Błąd",
        "js_conn_error": "Błąd połączenia.",
        "js_scanning": "🔍 Skanuję… (kilka sekund)",
        "js_scan_none": "Nic nie znaleziono (radio bywa zajęte — spróbuj ponownie).",
        "js_scan_fail": "Skan nie wyszedł — spróbuj ponownie.",
        "js_viz_stop": "⏻ Zatrzymaj wizualizer",
        "js_viz_start": "⏻ Uruchom wizualizer",
        "wifi_bad_ssid": "Nieprawidłowy SSID.",
        "wifi_bad_key": "Hasło WPA musi mieć 8–63 znaki (puste = sieć otwarta).",
        "wifi_no_slot": "Brak miejsca — DietPi mieści {n} sieci. Usuń jakąś.",
        "wifi_saved_msg": "Zapisano „{ssid}” (slot {slot}).",
        "wifi_reload_warn": " Uwaga: przeładowanie wpa_supplicant nie potwierdziło się — sieć zadziała najpóźniej po restarcie.",
        "wifi_empty_slot": "Pusty slot.",
        "wifi_rm_current": "To sieć, przez którą jesteś teraz połączony — nie usunę jej zdalnie.",
        "wifi_removed": "Usunięto „{ssid}”.",
        "viz_unknown": "Nieznany preset.",
        "viz_not_installed": "Wizualizer nie jest zainstalowany.",
        "viz_preset_set": "Preset „{label}” ustawiony.",
        "viz_stopped": "Wizualizer zatrzymany (do reboota / ręcznego startu).",
        "viz_started": "Wizualizer wystartowany.",
        "lang_set": "Przełączono na polski.",
        "preset_classic": "Klasyk",
        "preset_dense": "Gęsty",
        "preset_waves": "Fale",
        "preset_massive": "Masyw",
    },
}


def T(key):
    return STR.get(_lang, STR["en"]).get(key, STR["en"].get(key, key))


# ---------------------------------------------------------------------------
# Bluetooth control
# ---------------------------------------------------------------------------
_pair_lock = threading.Lock()
_pair_deadline = 0.0               # unix ts until which the pairing window lasts
_trusted = set()                   # cache: MACs already marked as trusted


def _run(cmd, timeout=8):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"__err__ {e}"


def _bt_show():
    return _run(["bluetoothctl", "show"])


def _connected_devices():
    """Returns a list [(mac, name)] of connected BT devices."""
    out = _run(["bluetoothctl", "devices", "Connected"])
    devices = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 3 and parts[0] == "Device":
            devices.append((parts[1], parts[2]))
    return devices


def _start_pairing(window=PAIR_WINDOW_SEC):
    """Makes the adapter discoverable/pairable for the duration of the window.

    Auto-accepting the pairing (Just Works) is handled by a separate persistent
    `bt-agent -c NoInputNoOutput` service — that is why we do NOT register our
    own agent here (two agents would collide). The headless Pi never has to
    confirm anything.
    """
    global _pair_deadline
    with _pair_lock:
        was_active = _pair_deadline > time.time()
        _pair_deadline = time.time() + window
        _run(["bluetoothctl", "power", "on"])
        _run(["bluetoothctl", "pairable", "on"])
        _run(["bluetoothctl", "discoverable", "on"])
        if was_active:
            return  # the closer thread is already running, we just extended the window

        def _closer():
            while time.time() < _pair_deadline:
                time.sleep(1)
            _run(["bluetoothctl", "discoverable", "off"])
            _run(["bluetoothctl", "pairable", "off"])

        threading.Thread(target=_closer, daemon=True).start()


def _auto_trust_loop():
    """Background: marks connected devices as trusted so they reconnect on their own."""
    while True:
        try:
            for mac, _name in _connected_devices():
                if mac not in _trusted:
                    _run(["bluetoothctl", "trust", mac])
                    _trusted.add(mac)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)


def _pair_seconds_left():
    left = int(_pair_deadline - time.time())
    return left if left > 0 else 0


def _service_active(name):
    return _run(["systemctl", "is-active", name]) == "active"


# ---------------------------------------------------------------------------
# Wi-Fi — managed through the DietPi network database (up to 5 slots).
#
# DietPi keeps known networks in /var/lib/dietpi/dietpi-wifi.db (bash format:
# aWIFI_SSID[n]='...', aWIFI_KEY[n]='...', aWIFI_KEYMGR[n]='WPA-PSK'),
# and `dietpi-wifidb 1` generates wpa_supplicant.conf from it. We write to the
# database instead of straight to wpa_supplicant so dietpi-config sees the
# same networks.
# ---------------------------------------------------------------------------
WIFI_DB = "/var/lib/dietpi/dietpi-wifi.db"
WIFI_APPLY_CMD = ["/boot/dietpi/func/dietpi-wifidb", "1"]
WIFI_SLOTS = 5
_WIFI_LINE = re.compile(r"^aWIFI_(\w+)\[(\d+)\]='(.*)'$")
_wifi_lock = threading.Lock()


def _wifi_db_read():
    """Returns {slot: {field: value}} from the DietPi network database."""
    slots = {}
    try:
        text = open(WIFI_DB, encoding="utf-8", errors="replace").read()
    except OSError:
        return slots
    for line in text.splitlines():
        m = _WIFI_LINE.match(line.strip())
        if m:
            field, idx, val = m.group(1), int(m.group(2)), m.group(3)
            slots.setdefault(idx, {})[field] = val.replace("'\\''", "'")
    return slots


def _wifi_db_write(slots):
    def esc(v):
        return str(v).replace("'", "'\\''")

    lines = []
    for i in range(WIFI_SLOTS):
        s = slots.get(i, {})
        lines.append(f"aWIFI_SSID[{i}]='{esc(s.get('SSID', ''))}'")
        lines.append(f"aWIFI_KEY[{i}]='{esc(s.get('KEY', ''))}'")
        lines.append(f"aWIFI_KEYMGR[{i}]='{esc(s.get('KEYMGR', 'WPA-PSK'))}'")
        # keep WPA-EAP etc. fields if the slot had them
        for f in ("PROTO", "PAIRWISE", "AUTH_ALG", "EAP", "IDENTITY",
                  "PASSWORD", "PHASE1", "PHASE2", "CERT"):
            if f in s:
                lines.append(f"aWIFI_{f}[{i}]='{esc(s[f])}'")
    tmp = WIFI_DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, WIFI_DB)


def _wifi_apply():
    """Regenerates wpa_supplicant.conf from the database and reloads wpa_supplicant.

    Reconfigure does not drop the active connection as long as the current
    network stays on the list — which is why /api/wifi/remove refuses to
    remove the current network.
    """
    out = _run(WIFI_APPLY_CMD, timeout=30)
    rec = _run(["wpa_cli", "-i", WIFI_IFACE, "reconfigure"], timeout=10)
    return {"apply": out, "reconfigure": rec,
            "reloaded": rec.strip().endswith("OK")}


def _wifi_current():
    """Current connection: {'ssid','signal','ip'} or None."""
    out = _run(["iw", "dev", WIFI_IFACE, "link"])
    m = re.search(r"^\s*SSID:\s*(.+)$", out, re.M)
    if not m:
        return None
    sig = re.search(r"signal:\s*(-?\d+)", out)
    ipo = _run(["ip", "-4", "-o", "addr", "show", WIFI_IFACE])
    ipm = re.search(r"inet\s+([\d.]+)", ipo)
    return {"ssid": m.group(1).strip(),
            "signal": int(sig.group(1)) if sig else None,
            "ip": ipm.group(1) if ipm else ""}


def _wifi_scan():
    """Scans the surroundings: [{'ssid','signal'}] sorted by signal strength."""
    out = _run(["iw", "dev", WIFI_IFACE, "scan"], timeout=25)
    if "__err__" in out or "busy" in out.lower():
        time.sleep(2)  # the radio can be momentarily busy (shared with BT)
        out = _run(["iw", "dev", WIFI_IFACE, "scan"], timeout=25)
    nets, sig = {}, None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("BSS "):
            sig = None
        elif s.startswith("signal:"):
            try:
                sig = float(s.split()[1])
            except (IndexError, ValueError):
                sig = None
        elif s.startswith("SSID:"):
            ssid = s[5:].strip()
            if ssid and "\\x00" not in ssid:
                cur = nets.get(ssid)
                val = sig if sig is not None else -100.0
                if cur is None or val > cur:
                    nets[ssid] = val
    return [{"ssid": k, "signal": round(v)}
            for k, v in sorted(nets.items(), key=lambda kv: -kv[1])]


def _tailscale_ip():
    out = _run(["tailscale", "ip", "-4"], timeout=5)
    first = out.splitlines()[0].strip() if out else ""
    return first if re.fullmatch(r"[\d.]+", first) else ""


# Setup-AP integration (ap-fallback/): while the device runs its fallback
# access point the shared radio cannot scan, so net-watch.sh snapshots the
# neighborhood right before raising the AP and we serve that snapshot instead.
AP_MARKER = "/run/pistream-ap.active"
AP_SCAN_CACHE = "/run/pistream-ap-scan.json"


def _wifi_scan_networks():
    if os.path.exists(AP_MARKER):
        try:
            with open(AP_SCAN_CACHE, encoding="utf-8") as fh:
                return json.load(fh).get("networks", [])
        except Exception:  # noqa: BLE001
            return []
    return _wifi_scan()


def _wifi_payload():
    slots = _wifi_db_read()
    saved = [{"slot": i, "ssid": s.get("SSID", ""), "keymgr": s.get("KEYMGR", "")}
             for i, s in sorted(slots.items()) if s.get("SSID")]
    return {"iface": WIFI_IFACE, "current": _wifi_current(), "saved": saved,
            "free_slots": WIFI_SLOTS - len(saved),
            "hostname": _HOSTNAME, "tailscale_ip": _tailscale_ip()}


def _wifi_add(ssid, key):
    """Adds/updates a network. Returns (ok, message)."""
    ssid, key = ssid.strip(), key.strip()
    if not ssid or len(ssid.encode()) > 32:
        return False, T("wifi_bad_ssid")
    if key and not 8 <= len(key) <= 63:
        return False, T("wifi_bad_key")
    with _wifi_lock:
        slots = _wifi_db_read()
        target = None
        for i, s in slots.items():
            if s.get("SSID") == ssid:
                target = i  # update an existing entry
                break
        if target is None:
            for i in range(WIFI_SLOTS):
                if not slots.get(i, {}).get("SSID"):
                    target = i
                    break
        if target is None:
            return False, T("wifi_no_slot").format(n=WIFI_SLOTS)
        slots[target] = {"SSID": ssid, "KEY": key,
                         "KEYMGR": "WPA-PSK" if key else "NONE"}
        _wifi_db_write(slots)
        res = _wifi_apply()
    msg = T("wifi_saved_msg").format(ssid=ssid, slot=target)
    if not res["reloaded"]:
        msg += T("wifi_reload_warn")
    return True, msg


def _wifi_remove(slot):
    with _wifi_lock:
        slots = _wifi_db_read()
        s = slots.get(slot)
        if not s or not s.get("SSID"):
            return False, T("wifi_empty_slot")
        cur = _wifi_current()
        if cur and cur["ssid"] == s["SSID"]:
            return False, T("wifi_rm_current")
        ssid = s["SSID"]
        slots[slot] = {}
        _wifi_db_write(slots)
        _wifi_apply()
    return True, T("wifi_removed").format(ssid=ssid)


# ---------------------------------------------------------------------------
# Visualizer (cava on HDMI) — look presets + start/stop.
# The panel rewrites /opt/pistream-visualizer/cava.conf and restarts the unit.
# Note: a visualizer update (visualizer/install.sh) overwrites the config
# file, so the preset falls back to the default then.
# ---------------------------------------------------------------------------
VIZ_CONF = "/opt/pistream-visualizer/cava.conf"
VIZ_SERVICE = "pistream-visualizer"

_VIZ_TEMPLATE = """# preset: {name} (managed by the Synchrofazotron panel — /settings page)
[general]
framerate = 30
autosens = 1
bars = 0
bar_width = {bar_width}
bar_spacing = {bar_spacing}

[input]
method = alsa
source = plughw:Loopback,1,0

[output]
; noncurses (not ncurses!) — the Debian cava package is built without ncurses
method = noncurses
channels = stereo

[color]
background = black
foreground = {color}

[smoothing]
{smoothing}
"""

# Preset ids are stable; display labels are translated (preset_* keys).
VIZ_PRESETS = {
    "classic": {"label_key": "preset_classic", "bar_width": 2, "bar_spacing": 1,
                "color": "cyan", "smoothing": "noise_reduction = 77"},
    "dense": {"label_key": "preset_dense", "bar_width": 1, "bar_spacing": 0,
              "color": "green",
              "smoothing": "monstercat = 1\nnoise_reduction = 70"},
    "waves": {"label_key": "preset_waves", "bar_width": 3, "bar_spacing": 1,
              "color": "blue", "smoothing": "waves = 1\nnoise_reduction = 80"},
    "massive": {"label_key": "preset_massive", "bar_width": 10, "bar_spacing": 2,
                "color": "magenta", "smoothing": "noise_reduction = 85"},
}
# Pre-rename ids (Polish) still found in configs written by older panels.
_VIZ_LEGACY_IDS = {"klasyk": "classic", "gesty": "dense",
                   "fale": "waves", "masyw": "massive"}


def _viz_state():
    installed = os.path.isfile(VIZ_CONF)
    preset = ""
    if installed:
        try:
            first = open(VIZ_CONF, encoding="utf-8").readline()
            m = re.search(r"# preset: (\w+)", first)
            preset = m.group(1) if m else "custom"
            preset = _VIZ_LEGACY_IDS.get(preset, preset)
        except OSError:
            pass
    return {"installed": installed, "active": _service_active(VIZ_SERVICE),
            "preset": preset,
            "presets": [{"id": k, "label": T(v["label_key"])}
                        for k, v in VIZ_PRESETS.items()]}


def _viz_set_preset(name):
    name = _VIZ_LEGACY_IDS.get(name, name)
    p = VIZ_PRESETS.get(name)
    if not p:
        return False, T("viz_unknown")
    if not os.path.isfile(VIZ_CONF):
        return False, T("viz_not_installed")
    with open(VIZ_CONF, "w", encoding="utf-8") as fh:
        fh.write(_VIZ_TEMPLATE.format(name=name, **{
            k: p[k] for k in ("bar_width", "bar_spacing", "color", "smoothing")}))
    _run(["systemctl", "try-restart", VIZ_SERVICE])
    return True, T("viz_preset_set").format(label=T(p["label_key"]))


def _viz_toggle():
    if _service_active(VIZ_SERVICE):
        _run(["systemctl", "stop", VIZ_SERVICE])
        return True, T("viz_stopped")
    _run(["systemctl", "start", VIZ_SERVICE])
    return True, T("viz_started")


# ---------------------------------------------------------------------------
# Detecting "what is playing right now"
#
# Architectural note: there is no central audio manager (like PulseAudio /
# PipeWire), so sources do NOT pause each other. On the HDMI output (bcm2835,
# 8 subdevices) they play in parallel and get MIXED. On a hardware DAC
# (1 subdevice) the first one grabs the output and the rest get "device busy".
# This indicator shows what is active so you know what to stop.
# ---------------------------------------------------------------------------
_lms_playerid = None


def _lms_request(params):
    body = json.dumps({"id": 1, "method": "slim.request", "params": params}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{LMS_PORT}/jsonrpc.js", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read().decode()).get("result", {})


def _lms_state():
    """Returns {'mode','title'} of the Squeezelite player, or None."""
    global _lms_playerid
    try:
        if not _lms_playerid:
            loop = _lms_request(["", ["players", "0", "10"]]).get("players_loop", [])
            if loop:
                _lms_playerid = loop[0]["playerid"]
        if not _lms_playerid:
            return None
        res = _lms_request([_lms_playerid, ["status", "-", 1, "tags:aN"]])
        title = ""
        rm = res.get("remoteMeta") or {}
        title = rm.get("title") or ""
        if not title:
            loop = res.get("playlist_loop") or []
            if loop:
                title = loop[0].get("title", "")
        return {"mode": res.get("mode", "stop"), "title": title}
    except Exception:  # noqa: BLE001
        return None


def _bt_streams():
    """List of A2DP streams: [{'mac','running'}] (Running=true => actually playing)."""
    streams = []
    for path in _run(["bluealsa-cli", "list-pcms"]).splitlines():
        path = path.strip()
        if "a2dp" not in path:
            continue
        info = _run(["bluealsa-cli", "info", path])
        mac = ""
        if "/dev_" in path:
            mac = path.split("/dev_")[1].split("/")[0].replace("_", ":")
        streams.append({"mac": mac, "running": "Running: true" in info})
    return streams


def _alsa_playback_units(running_only=True):
    """Set of systemd units holding an ALSA playback stream.

    running_only=True  -> only streams actively playing (state: RUNNING)
    running_only=False -> any open stream, including paused/prepared ones
                          (a paused source still blocks a single-substream DAC)
    """
    active = set()
    for f in glob.glob("/proc/asound/card*/pcm*p/sub*/status"):
        try:
            txt = open(f).read()
        except Exception:  # noqa: BLE001
            continue
        if running_only:
            if "state: RUNNING" not in txt:
                continue
        elif txt.strip() == "closed":
            continue
        m = re.search(r"owner_pid\s*:\s*(\d+)", txt)
        if not m:
            continue
        try:
            cg = open(f"/proc/{m.group(1)}/cgroup").read()
        except Exception:  # noqa: BLE001
            continue
        um = re.search(r"([A-Za-z0-9_.@-]+\.service)", cg)
        if um:
            active.add(um.group(1))
    return active


def _alsa_active_units():
    return _alsa_playback_units(running_only=True)


def _active_sources(connected):
    """Returns the list of sources with their playback state."""
    sources = []
    lms = _lms_state()
    if lms is not None:
        state = {"play": T("state_playing"),
                 "pause": T("state_paused")}.get(lms["mode"], T("state_idle"))
        sources.append({"name": "LMS (radio/TIDAL)", "playing": lms["mode"] == "play",
                        "state": state, "detail": lms.get("title", "")})

    conn = dict(connected)
    bt_playing, bt_detail = False, ""
    for s in _bt_streams():
        if s["running"]:
            bt_playing = True
            bt_detail = conn.get(s["mac"], s["mac"])
    if conn or bt_playing:
        sources.append({"name": "Bluetooth", "playing": bt_playing,
                        "state": T("state_playing") if bt_playing else T("state_connected"),
                        "detail": bt_detail or ", ".join(conn.values())})

    units = _alsa_active_units()
    unit_map = [("shairport-sync.service", "AirPlay", "airplay", True)]
    if SHOW_SPOTIFY:
        unit_map.append(("raspotify.service", "Spotify", "spotify", False))
    for unit, label, sid, ctl in unit_map:
        if unit in units:
            sources.append({"name": label, "id": sid, "playing": True,
                            "state": T("state_playing"), "detail": "",
                            "controllable": ctl})

    # id + controllable for LMS/BT (added above without those fields)
    for s in sources:
        s.setdefault("controllable", True)
        s.setdefault("id", {"LMS (radio/TIDAL)": "lms",
                            "Bluetooth": "bt"}.get(s["name"], ""))
    return sources


# ---------------------------------------------------------------------------
# Auto-pause arbiter ("new playback wins")
#
# On a hardware DAC only one source can hold the output; without arbitration
# a newly started source plays into the void while the old one keeps the
# device. This loop watches for a source that just started playing and pauses
# the ones that were playing before (LMS via jsonrpc, BT via AVRCP, AirPlay
# via MPRIS; Spotify/librespot has no local control and cannot be paused).
#
# Companion fix outside this file: squeezelite runs with `-C 5` (setup.sh),
# so a *paused* LMS releases the DAC after 5 s instead of holding it forever.
# ---------------------------------------------------------------------------
_PAUSABLE = ("lms", "bt", "airplay")


def _bt_ensure_output():
    """BT just started playing: make sure its audio actually reaches the DAC.

    bluealsa-aplay opens the ALSA device once per stream and does NOT retry if
    that fails (device busy). So: wait until the other sources release the
    device (squeezelite closes it a few seconds after pause), then — if
    bluealsa-aplay still holds no playback stream — restart it, which makes it
    reattach to the still-running BT transport.
    """
    for _ in range(10):
        others = _alsa_playback_units(running_only=False) - {"bluealsa-aplay.service"}
        if not others:
            break
        time.sleep(1)
    time.sleep(0.5)
    if "bluealsa-aplay.service" not in _alsa_playback_units(running_only=False):
        _run(["systemctl", "restart", "bluealsa-aplay"])


def _autopause_loop():
    prev = None
    while True:
        try:
            sources = _active_sources(_connected_devices())
            cur = {s["id"]: s["playing"] for s in sources if s.get("id")}
            if prev is not None:
                new = {i for i, p in cur.items() if p and not prev.get(i)}
                old = {i for i, p in cur.items() if p and prev.get(i)} - new
                if new:
                    for i in old:
                        if i in _PAUSABLE:
                            _control(i, "pause")
                    if "bt" in new:
                        _bt_ensure_output()
            prev = cur
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)


# ---------------------------------------------------------------------------
# Playback control (play/pause) per source
# ---------------------------------------------------------------------------
def _bt_player_path():
    m = re.search(r"/org/bluez/hci0/dev_[0-9A-Fa-f_]+/player\d+",
                  _run(["busctl", "tree", "org.bluez"]))
    return m.group(0) if m else None


def _control(source, action):
    """action: 'play' | 'pause' | 'toggle'. Returns True when a command was sent."""
    if source == "lms":
        if not (_lms_playerid or _lms_state()):
            return False
        if action == "toggle":
            st = _lms_state() or {}
            action = "pause" if st.get("mode") == "play" else "play"
        cmd = ["pause", "1"] if action == "pause" else ["play"]
        try:
            _lms_request([_lms_playerid, cmd])
            return True
        except Exception:  # noqa: BLE001
            return False

    if source == "bt":
        p = _bt_player_path()
        if not p:
            return False
        if action == "toggle":
            st = _run(["busctl", "get-property", "org.bluez", p,
                       "org.bluez.MediaPlayer1", "Status"])
            action = "pause" if "playing" in st else "play"
        meth = "Pause" if action == "pause" else "Play"
        return "__err__" not in _run(
            ["busctl", "call", "org.bluez", p, "org.bluez.MediaPlayer1", meth])

    if source == "airplay":
        meth = {"pause": "Pause", "play": "Play"}.get(action, "PlayPause")
        return "__err__" not in _run(
            ["busctl", "call", "org.mpris.MediaPlayer2.ShairportSync",
             "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", meth])

    return False


def status_payload():
    show = _bt_show()
    connected = _connected_devices()
    sources = _active_sources(connected)
    return {
        "device_name": DEVICE_NAME,
        "lang": _lang,
        "autopause": AUTOPAUSE,
        "bt_powered": "Powered: yes" in show,
        "bt_discoverable": "Discoverable: yes" in show,
        "pair_seconds_left": _pair_seconds_left(),
        "connected": [{"mac": m, "name": n} for m, n in connected],
        "sources": sources,
        "playing_count": sum(1 for s in sources if s.get("playing")),
        "services": {
            s: _service_active(s) for s in (
                ("bluetooth", "bluealsa", "squeezelite",
                 "shairport-sync", "lyrionmusicserver")
                + (("raspotify",) if SHOW_SPOTIFY else ())
            )
        },
    }


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------
_T_PLACEHOLDER = re.compile(r"\{\{T:(\w+)\}\}")


def _fill(template, host_header):
    lms_host = host_header.split(":")[0] if host_header else DEVICE_NAME
    lms_url = f"http://{lms_host}:{LMS_PORT}/material"
    html = template
    if not SHOW_SPOTIFY:
        html = re.sub(r"<!--SPOTIFY-->.*?<!--/SPOTIFY-->", "", html, flags=re.S)
    # translations first — translated strings may themselves contain {{DEVICE}} etc.
    html = _T_PLACEHOLDER.sub(lambda m: T(m.group(1)), html)
    html = html.replace("{{LANG}}", _lang)
    html = html.replace("{{DEVICE}}", DEVICE_NAME)
    html = html.replace("{{LMS_URL}}", lms_url)
    html = html.replace("{{PLAYER}}", SQUEEZELITE_PLAYER)
    html = html.replace("{{PAIR_WIN}}", str(PAIR_WINDOW_SEC))
    return html


def render_page(host_header):
    return _fill(PAGE_TEMPLATE, host_header)


def render_settings(host_header):
    return _fill(SETTINGS_TEMPLATE, host_header)


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="{{LANG}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{DEVICE}} — {{T:title_panel}}</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
    background: #0f1216; color: #e7ecf2; line-height: 1.5;
    padding: 20px 16px 48px;
  }
  .wrap { max-width: 620px; margin: 0 auto; }
  h1 { font-size: 1.7rem; margin: 4px 0 2px; }
  .sub { color: #8b97a6; margin: 0 0 20px; font-size: .95rem; }
  .card {
    background: #171c23; border: 1px solid #232b35; border-radius: 14px;
    padding: 16px 18px; margin: 12px 0;
  }
  .card h2 { font-size: 1.05rem; margin: 0 0 8px; display:flex; align-items:center; gap:8px;}
  .card p { margin: 6px 0; color: #c4cad3; }
  .muted { color: #8b97a6; font-size: .9rem; }
  a { color: #6db3ff; }
  .btn {
    display: block; width: 100%; border: 0; border-radius: 12px;
    padding: 18px; font-size: 1.1rem; font-weight: 600; cursor: pointer;
    background: #2563eb; color: #fff; transition: background .15s;
  }
  .btn:hover { background: #1d4ed8; }
  .btn.active { background: #059669; }
  .btn:disabled { opacity: .8; cursor: default; }
  .pill {
    display:inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: .8rem; font-weight: 600;
  }
  .on  { background:#0c3; color:#04210f; }
  .off { background:#333b46; color:#9aa6b3; }
  .status-line { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:10px;}
  .step { margin: 4px 0 4px 2px; }
  .num { display:inline-block; width:22px; height:22px; border-radius:50%;
    background:#2563eb; color:#fff; text-align:center; font-size:.8rem;
    line-height:22px; margin-right:8px; font-weight:700;}
  code { background:#0b0e12; padding:1px 6px; border-radius:6px; font-size:.9em;}
  .note { border-left:3px solid #b8860b; padding-left:12px; }
  .srow { display:flex; align-items:center; gap:10px; padding:8px 0;
    border-bottom:1px solid #232b35; }
  .srow:last-child { border-bottom:0; }
  .srow .info { flex:1; min-width:0; }
  .srow .info .det { color:#8b97a6; font-size:.85rem;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .tbtn { flex:none; width:52px; height:44px; border:0; border-radius:10px;
    background:#2b3440; color:#fff; font-size:1.2rem; cursor:pointer; }
  .tbtn:hover { background:#374151; }
  .tbtn.playing { background:#059669; }
  .tbtn:disabled { opacity:.35; cursor:default; }
</style>
</head>
<body>
<div class="wrap">
  <div style="display:flex; align-items:baseline; justify-content:space-between;">
    <h1>🎵 {{DEVICE}}</h1>
    <a href="/settings" style="text-decoration:none; font-size:1.3rem;" title="{{T:settings_link_title}}">⚙️</a>
  </div>
  <p class="sub">{{T:sub_panel}}</p>

  <div class="card">
    <h2>{{T:now_playing}}</h2>
    <div id="warn" class="note" style="display:none; margin:0 0 10px;">
      {{T:warn_multi}}
    </div>
    <div id="sources"><p class="muted">…</p></div>
    <p class="muted" style="margin-top:8px;">{{T:sources_note}}</p>
  </div>

  <div class="card">
    <h2>{{T:bt_head}}</h2>
    <p>{{T:bt_intro}}</p>
    <button id="pairBtn" class="btn" onclick="pair()">{{T:bt_button}}</button>
    <div class="status-line">
      <span>{{T:bt_status}}</span>
      <span id="btState" class="pill off">…</span>
      <span id="btConn" class="muted"></span>
    </div>
    <p class="muted step">{{T:bt_after}}</p>
  </div>

  <!--SPOTIFY-->
  <div class="card">
    <h2>{{T:spotify_head}}</h2>
    <p><span class="num">1</span>{{T:spotify_1}}</p>
    <p><span class="num">2</span>{{T:spotify_2}}</p>
    <p class="muted">{{T:spotify_note}}</p>
  </div>
  <!--/SPOTIFY-->

  <div class="card">
    <h2>{{T:airplay_head}}</h2>
    <p><span class="num">1</span>{{T:airplay_1}}</p>
    <p><span class="num">2</span>{{T:airplay_2}}</p>
  </div>

  <div class="card">
    <h2>{{T:lms_head}}</h2>
    <p><span class="num">1</span>{{T:lms_1}}</p>
    <p><span class="num">2</span>{{T:lms_2}}</p>
    <p>{{T:lms_web}} <a href="{{LMS_URL}}">{{LMS_URL}}</a> {{T:lms_web2}}</p>
  </div>

  <div class="card note">
    <h2>{{T:audio_note_head}}</h2>
    <p class="muted">{{T:audio_note}}</p>
  </div>

  <p class="muted" style="text-align:center; margin-top:24px;">
    {{T:players_label}} <span id="svc"></span>
  </p>
</div>

<script>
let timer = null;

async function refresh() {
  try {
    const r = await fetch('/api/status', {cache:'no-store'});
    const s = await r.json();
    const btState = document.getElementById('btState');
    const left = s.pair_seconds_left;
    if (left > 0) {
      btState.textContent = '{{T:js_pairing}}' + left + 's';
      btState.className = 'pill on';
      setBtn(true, left);
    } else {
      btState.textContent = s.bt_powered ? '{{T:js_ready}}' : '{{T:js_off}}';
      btState.className = 'pill ' + (s.bt_powered ? 'on' : 'off');
      setBtn(false, 0);
    }
    const conn = s.connected || [];
    document.getElementById('btConn').textContent =
      conn.length ? ('{{T:js_connected}}' + conn.map(d=>d.name).join(', ')) : '';

    // "Now playing"
    const src = s.sources || [];
    const box = document.getElementById('sources');
    if (!src.length) {
      box.innerHTML = '<p class="muted">{{T:js_silence}}</p>';
    } else {
      box.innerHTML = src.map(x => {
        const dot = x.playing ? '🟢' : '⚪';
        const det = x.detail
          ? '<div class="det">' + escapeHtml(x.detail) + '</div>' : '';
        let btn;
        if (x.controllable && x.id) {
          const icon = x.playing ? '⏸' : '▶';
          const cls = 'tbtn' + (x.playing ? ' playing' : '');
          btn = '<button class="' + cls + '" title="play/pause" ' +
                'onclick="ctrl(\\'' + x.id + '\\')">' + icon + '</button>';
        } else {
          btn = '<button class="tbtn" disabled title="{{T:js_ctrl_hint}}">▶</button>';
        }
        return '<div class="srow"><div class="info">' + dot + ' <b>' +
               escapeHtml(x.name) + '</b> — ' + x.state + det + '</div>' + btn + '</div>';
      }).join('');
    }
    document.getElementById('warn').style.display =
      (s.playing_count >= 2) ? 'block' : 'none';

    const svc = s.services || {};
    document.getElementById('svc').textContent =
      Object.keys(svc).map(k => (svc[k]?'🟢':'🔴')+k).join('  ');
  } catch(e) { /* ignore */ }
}

function setBtn(active, left) {
  const b = document.getElementById('pairBtn');
  if (active) {
    b.classList.add('active');
    b.textContent = '{{T:js_pair_active_pre}}' + left + '{{T:js_pair_active_suf}}';
  } else {
    b.classList.remove('active');
    b.textContent = '{{T:bt_button}}';
  }
}

async function pair() {
  const b = document.getElementById('pairBtn');
  b.disabled = true;
  try { await fetch('/api/pair', {method:'POST'}); } catch(e){}
  b.disabled = false;
  refresh();
}

async function ctrl(id) {
  try {
    await fetch('/api/control', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({source:id, action:'toggle'})
    });
  } catch(e){}
  setTimeout(refresh, 500);
}

function escapeHtml(s) {
  return (s||'').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


SETTINGS_TEMPLATE = """<!DOCTYPE html>
<html lang="{{LANG}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{DEVICE}} — {{T:title_settings}}</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
    background: #0f1216; color: #e7ecf2; line-height: 1.5;
    padding: 20px 16px 48px;
  }
  .wrap { max-width: 620px; margin: 0 auto; }
  h1 { font-size: 1.7rem; margin: 4px 0 2px; }
  .sub { color: #8b97a6; margin: 0 0 20px; font-size: .95rem; }
  .card {
    background: #171c23; border: 1px solid #232b35; border-radius: 14px;
    padding: 16px 18px; margin: 12px 0;
  }
  .card h2 { font-size: 1.05rem; margin: 0 0 8px; }
  .card p { margin: 6px 0; color: #c4cad3; }
  .muted { color: #8b97a6; font-size: .9rem; }
  a { color: #6db3ff; }
  input {
    width: 100%; padding: 12px; margin: 6px 0; border-radius: 10px;
    border: 1px solid #2b3440; background: #0b0e12; color: #e7ecf2;
    font-size: 1rem;
  }
  .btn {
    display: block; width: 100%; border: 0; border-radius: 12px;
    padding: 14px; font-size: 1rem; font-weight: 600; cursor: pointer;
    background: #2563eb; color: #fff; margin-top: 8px;
  }
  .btn:hover { background: #1d4ed8; }
  .btn.sec { background: #2b3440; }
  .btn.sec:hover { background: #374151; }
  .btn.active { background: #059669; }
  .btn:disabled { opacity: .6; cursor: default; }
  .row { display:flex; align-items:center; gap:10px; padding:8px 0;
    border-bottom:1px solid #232b35; }
  .row:last-child { border-bottom:0; }
  .row .info { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis;
    white-space:nowrap; }
  .xbtn { flex:none; border:0; border-radius:10px; width:44px; height:38px;
    background:#3a2328; color:#f0a5a5; font-size:1rem; cursor:pointer; }
  .xbtn:hover { background:#4c2b32; }
  .pill { display:inline-block; padding:2px 10px; border-radius:999px;
    font-size:.8rem; font-weight:600; }
  .on  { background:#0c3; color:#04210f; }
  .off { background:#333b46; color:#9aa6b3; }
  #msg { min-height: 1.4em; }
  .netbtn { text-align:left; }
  code { background:#0b0e12; padding:1px 6px; border-radius:6px; font-size:.9em;}
  .lrow { display:flex; gap:10px; }
  .lrow .btn { margin-top: 0; }
</style>
</head>
<body>
<div class="wrap">
  <div style="display:flex; align-items:baseline; justify-content:space-between;">
    <h1>{{T:settings_head}}</h1>
    <a href="/" style="text-decoration:none;">{{T:back_to_panel}}</a>
  </div>
  <p class="sub">{{DEVICE}}</p>

  <div class="card">
    <h2>{{T:wifi_now_head}}</h2>
    <p id="wifiNow" class="muted">…</p>
    <p id="netInfo" class="muted"></p>
  </div>

  <div class="card">
    <h2>{{T:wifi_saved_head}}</h2>
    <p class="muted">{{T:wifi_saved_note}}</p>
    <div id="saved"><p class="muted">…</p></div>
  </div>

  <div class="card">
    <h2>{{T:wifi_add_head}}</h2>
    <p class="muted">{{T:wifi_add_note}}</p>
    <input id="ssid" placeholder="{{T:wifi_ssid_ph}}" autocomplete="off">
    <input id="key" type="password" placeholder="{{T:wifi_key_ph}}"
           autocomplete="new-password">
    <button class="btn" id="addBtn" onclick="addNet()">{{T:wifi_save_btn}}</button>
    <button class="btn sec" id="scanBtn" onclick="scan()">{{T:wifi_scan_btn}}</button>
    <div id="scanOut"></div>
    <p id="msg" class="muted"></p>
  </div>

  <div class="card" id="vizCard" style="display:none;">
    <h2>{{T:viz_head}}</h2>
    <p class="muted">{{T:viz_note}}</p>
    <div id="vizPresets"></div>
    <button class="btn sec" id="vizToggle" onclick="vizToggle()">…</button>
    <p id="vizMsg" class="muted"></p>
  </div>

  <div class="card">
    <h2>{{T:lang_head}}</h2>
    <p class="muted">{{T:lang_note}}</p>
    <div class="lrow">
      <button class="btn LANGBTN_en" onclick="setLang('en')">English</button>
      <button class="btn LANGBTN_pl" onclick="setLang('pl')">Polski</button>
    </div>
  </div>

  <div class="card">
    <h2>{{T:how_head}}</h2>
    <p class="muted">{{T:how_note}}</p>
  </div>
</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/api/wifi', {cache:'no-store'});
    const w = await r.json();
    const cur = w.current;
    document.getElementById('wifiNow').innerHTML = cur
      ? '<span class="pill on">{{T:js_wifi_connected}}</span> <b>' + escapeHtml(cur.ssid) + '</b>'
        + (cur.ip ? ' — ' + cur.ip : '')
        + (cur.signal != null ? ' <span class="muted">(' + cur.signal + ' dBm)</span>' : '')
      : '<span class="pill off">{{T:js_wifi_none}}</span>';
    // addresses "just in case" — how to reach the panel if MagicDNS fails
    const bits = [];
    if (cur && cur.ip) bits.push('{{T:js_lan_ip}}<code>' + cur.ip + '</code>');
    if (w.tailscale_ip) bits.push('{{T:js_ts_ip}}<code>' + w.tailscale_ip + '</code>');
    if (w.hostname) bits.push('<code>' + escapeHtml(w.hostname) + '</code>');
    document.getElementById('netInfo').innerHTML = bits.join(' · ');
    const box = document.getElementById('saved');
    const saved = w.saved || [];
    box.innerHTML = saved.length ? saved.map(s =>
      '<div class="row"><div class="info">' +
      (cur && cur.ssid === s.ssid ? '🟢 ' : '') + '<b>' + escapeHtml(s.ssid) + '</b>' +
      ' <span class="muted">{{T:js_slot}}' + s.slot + '</span></div>' +
      '<button class="xbtn" title="{{T:js_remove}}" onclick="removeNet(' + s.slot + ',\\'' +
      escapeHtml(s.ssid).replace(/'/g, "\\\\'") + '\\')">🗑</button></div>'
    ).join('') : '<p class="muted">{{T:js_no_saved}}</p>';
  } catch(e) {}
}

async function addNet() {
  const ssid = document.getElementById('ssid').value;
  const key = document.getElementById('key').value;
  const b = document.getElementById('addBtn');
  b.disabled = true; msg('{{T:js_saving}}');
  try {
    const r = await fetch('/api/wifi/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ssid, key})
    });
    const j = await r.json();
    msg(j.message || (j.ok ? 'OK' : '{{T:js_error}}'));
    if (j.ok) { document.getElementById('ssid').value='';
                document.getElementById('key').value=''; }
  } catch(e) { msg('{{T:js_conn_error}}'); }
  b.disabled = false;
  refresh();
}

async function removeNet(slot, ssid) {
  if (!confirm('{{T:js_rm_pre}}' + ssid + '{{T:js_rm_suf}}')) return;
  try {
    const r = await fetch('/api/wifi/remove', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({slot})
    });
    const j = await r.json();
    msg(j.message || '');
  } catch(e) { msg('{{T:js_conn_error}}'); }
  refresh();
}

async function scan() {
  const b = document.getElementById('scanBtn');
  b.disabled = true; b.textContent = '{{T:js_scanning}}';
  try {
    const r = await fetch('/api/wifi/scan', {cache:'no-store'});
    const j = await r.json();
    const nets = j.networks || [];
    document.getElementById('scanOut').innerHTML = nets.length
      ? nets.map(n =>
          '<button class="btn sec netbtn" onclick="pick(\\'' +
          escapeHtml(n.ssid).replace(/'/g, "\\\\'") + '\\')">' +
          escapeHtml(n.ssid) + ' <span class="muted">' + n.signal + ' dBm</span></button>'
        ).join('')
      : '<p class="muted">{{T:js_scan_none}}</p>';
  } catch(e) { msg('{{T:js_scan_fail}}'); }
  b.disabled = false; b.textContent = '{{T:wifi_scan_btn}}';
}

function pick(ssid) {
  document.getElementById('ssid').value = ssid;
  document.getElementById('key').focus();
}

async function vizRefresh() {
  try {
    const r = await fetch('/api/viz', {cache:'no-store'});
    const v = await r.json();
    if (!v.installed) return;
    document.getElementById('vizCard').style.display = '';
    document.getElementById('vizPresets').innerHTML = (v.presets||[]).map(p =>
      '<button class="btn ' + (p.id === v.preset ? '' : 'sec') + '" ' +
      'onclick="vizPreset(\\'' + p.id + '\\')">' + escapeHtml(p.label) +
      (p.id === v.preset ? ' ✓' : '') + '</button>'
    ).join('');
    document.getElementById('vizToggle').textContent =
      v.active ? '{{T:js_viz_stop}}' : '{{T:js_viz_start}}';
  } catch(e) {}
}

async function vizPreset(name) {
  try {
    const r = await fetch('/api/viz/preset', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) {}
  vizRefresh();
}

async function vizToggle() {
  try {
    const r = await fetch('/api/viz/toggle', {method:'POST'});
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) {}
  setTimeout(vizRefresh, 500);
}

async function setLang(lang) {
  try {
    await fetch('/api/lang', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({lang})
    });
  } catch(e) {}
  location.reload();
}

function msg(t) { document.getElementById('msg').textContent = t; }

function escapeHtml(s) {
  return (s||'').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// highlight the active language button
document.querySelector('.LANGBTN_{{LANG}}').classList.add('active');
document.querySelectorAll('[class*="LANGBTN_"]').forEach(b => {
  if (!b.classList.contains('active')) b.classList.add('sec');
});

refresh();
vizRefresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SynchrofazotronPanel/1.0"

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001
            return {}

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, render_page(self.headers.get("Host", "")))
        elif self.path == "/settings":
            self._send(200, render_settings(self.headers.get("Host", "")))
        elif self.path == "/api/status":
            self._send(200, json.dumps(status_payload()), "application/json")
        elif self.path == "/api/wifi":
            self._send(200, json.dumps(_wifi_payload()), "application/json")
        elif self.path == "/api/wifi/scan":
            self._send(200, json.dumps({"networks": _wifi_scan_networks()}),
                       "application/json")
        elif self.path == "/api/viz":
            self._send(200, json.dumps(_viz_state()), "application/json")
        elif self.path == "/api/lang":
            self._send(200, json.dumps({"lang": _lang, "available": LANGS}),
                       "application/json")
        elif self.path == "/healthz":
            self._send(200, "ok", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path == "/api/pair":
            _start_pairing()
            self._send(200, json.dumps({"ok": True, "seconds": _pair_seconds_left()}),
                       "application/json")
        elif self.path == "/api/control":
            body = self._json_body()
            ok = _control(str(body.get("source", "")), str(body.get("action", "toggle")))
            self._send(200, json.dumps({"ok": ok}), "application/json")
        elif self.path == "/api/wifi/add":
            body = self._json_body()
            ok, message = _wifi_add(str(body.get("ssid", "")), str(body.get("key", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/wifi/remove":
            body = self._json_body()
            try:
                slot = int(body.get("slot", -1))
            except (TypeError, ValueError):
                slot = -1
            ok, message = _wifi_remove(slot)
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/preset":
            body = self._json_body()
            ok, message = _viz_set_preset(str(body.get("name", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/toggle":
            ok, message = _viz_toggle()
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/lang":
            body = self._json_body()
            ok = _lang_set(str(body.get("lang", "")))
            self._send(200, json.dumps({"ok": ok, "lang": _lang,
                                        "message": T("lang_set") if ok else ""}),
                       "application/json")
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args):  # keep the logs quiet
        pass


def main():
    threading.Thread(target=_auto_trust_loop, daemon=True).start()
    if AUTOPAUSE:
        threading.Thread(target=_autopause_loop, daemon=True).start()
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"Synchrofazotron panel at http://{BIND}:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
