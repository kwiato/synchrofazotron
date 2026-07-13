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
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Configuration (tweak to taste; everything can be overridden via env)
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PISTREAM_PANEL_PORT", "8787"))
BIND = os.environ.get("PISTREAM_PANEL_BIND", "0.0.0.0")
REPO = os.environ.get("PISTREAM_REPO", "kwiato/synchrofazotron")
BRANCH = os.environ.get("PISTREAM_BRANCH", "main")
VERSION = "0.70.18"                 # About version; CI auto-bumps the patch part
                                   # (build-panel.yml) — bump minor/major by hand

_HOSTNAME = socket.gethostname() or "Synchrofazotron"
# Runtime-changeable device identity. A name set from /settings is persisted to
# NAME_FILE (next to the script, survives updates) and wins over the env
# default, the same way the language choice does.
NAME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "name")
try:
    _saved_name = open(NAME_FILE, encoding="utf-8").read().strip() or None
except OSError:
    _saved_name = None
DEVICE_NAME = _saved_name or os.environ.get("PISTREAM_NAME") or _HOSTNAME  # BT / AirPlay name
LMS_PORT = 9000                    # Lyrion Music Server web UI port
SQUEEZELITE_PLAYER = _saved_name or os.environ.get("PISTREAM_LMS_PLAYER") or _HOSTNAME
PAIR_WINDOW_SEC = 180             # how long the Pi stays visible while pairing
SHOW_SPOTIFY = os.environ.get("PISTREAM_SPOTIFY", "0") == "1"  # raspotify not installed
WIFI_IFACE = os.environ.get("PISTREAM_WIFI_IFACE", "wlan0")
# Auto-pause: when a new source starts playing, pause the previous one.
# Essential on a hardware DAC (single substream — sources cannot mix there).
AUTOPAUSE = os.environ.get("PISTREAM_AUTOPAUSE", "1") == "1"

# Sandbox / dev mode. When on, no host-mutating command runs — every _run()
# is a no-op, so previewing the UI on a laptop can never touch the real system
# (no tailscale/hostname/systemctl/bluetoothctl/reboot/update). The panel still
# renders; status just reads back empty. The real deployment always runs from
# /opt/pistream-panel (installed there by web/install.sh and launched by the
# systemd unit), so anything running from elsewhere — a repo checkout on any
# OS — defaults to the safe sandbox. Force either way with PISTREAM_DEV=1/0.
_ON_DEVICE = os.path.abspath(__file__).startswith("/opt/pistream-panel")
DEV_MODE = os.environ.get("PISTREAM_DEV", "0" if _ON_DEVICE else "1") == "1"

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
        "tab_now": "Now playing",
        "tab_viz": "Visualizer",
        "tab_radio": "Radio",
        "radio_browse": "Browse",
        "radio_search": "Search",
        "radio_fav": "Favorites",
        "radio_search_ph": "Search stations, genres…",
        "radio_empty": "Nothing here.",
        "radio_fav_empty": "No favorites yet. Tap the star on a station to add it.",
        "radio_loading": "Loading…",
        "radio_added": "Added to favorites",
        "radio_removed": "Removed from favorites",
        "radio_play_err": "Could not play that station",
        "radio_unavailable": "Lyrion Music Server is not reachable.",
        "st_wifi_off": "Not connected",
        "st_bt_ready": "Ready",
        "st_bt_off": "Off",
        "st_bt_pairing": "Pairing…",
        "device_head": "Device",
        "device_connected": "Connected device",
        "switch_device": "Switch device",
        "pair_short": "Pair",
        "wifi_none_short": "Wi-Fi",
        "wifi_header_title": "Wi-Fi — open network settings",
        "sheet_sources": "Sources",
        "viz_more": "Preset editing and shader upload live in settings.",
        "how_connect_head": "How to connect sources",
        # settings v2 (sections / tailscale / source switches)
        "nav_customize": "Customize",
        "nav_connections": "Connections",
        "vol_head": "Volume",
        "vol_none": "No source is playing right now.",
        "exp_head": "Experimental",
        "exp_note": "Rough edges live here. Handy, but may change or misbehave.",
        "exp_normalize": "Customize visualizer normalization",
        "exp_normalize_note": "Off = the shipped auto-gain (lively at any "
                              "playback volume). On = tune how each engine "
                              "tracks the signal.",
        "viz_normalize_on": "Visualizer normalization: custom parameters applied.",
        "viz_normalize_off": "Visualizer normalization back to defaults.",
        "norm_autosens": "Auto sensitivity (autosens)",
        "norm_sensitivity": "Sensitivity",
        "norm_boost": "Max boost",
        "norm_target": "Target level",
        "nav_config": "Config",
        "nav_sources": "Sources",
        "nav_viz": "Visualizer",
        "nav_about": "About",
        "wifi_add_btn": "Add a network",
        "modal_cancel": "Cancel",
        "ts_head": "Tailscale",
        "ts_note": "Connect to Tailscale for secure remote management — the panel works from anywhere, no ports to open.",
        "ts_missing": "Tailscale is not installed on the device.",
        "ts_up_ok": "Tailscale connected.",
        "ts_down_ok": "Tailscale disconnected.",
        "ts_login": "Tailscale needs a one-time login — run tailscale up on the device.",
        "ts_fail": "The tailscale command failed.",
        "src_not_installed": "not installed",
        "src_on_msg": "{name} enabled.",
        "src_off_msg": "{name} disabled.",
        "src_fail_msg": "Could not switch {name} — check the service dots.",
        "src_disabled_hint": "Disabled — flip the switch to use this source.",
        "src_unknown": "Unknown source.",
        "js_src_off_pre": "Disable ",
        "js_src_off_suf": "? Playback from this source will stop.",
        "bt_forget_title": "Forget device",
        "js_bt_forget_pre": "Forget \"",
        "js_bt_forget_suf": "\"? The phone will have to pair again.",
        "bt_forgot": "Device forgotten.",
        "viz_studio_head": "Shader studio",
        "viz_studio_note": "Design your own shader in the browser studio, then drop the downloaded .frag file onto the shaders card.",
        "viz_studio_btn": "Open the studio",
        "about_desc": "Synchrofazotron turns a Raspberry Pi into a multi-source audio player: Bluetooth, AirPlay, Spotify Connect and TIDAL/radio/library via Lyrion Music Server, plus a music visualizer on HDMI.",
        "about_repo": "Source code, docs and issues:",
        "about_license": "Free software, licensed under GPL-3.0.",
        "about_version": "Version",
        "about_app_version": "App version (Google Play)",
        "now_playing": "Now playing",
        "warn_multi": "Multiple sources are playing at once — the first one owns the DAC, the rest play into the void. Stop the ones you do not need.",
        "bt_head": "Bluetooth",
        "bt_intro": "Tap to make the device visible and ready to pair for <b>{{PAIR_WIN}} seconds</b>. Then on your phone: Bluetooth → select <b>{{DEVICE}}</b>.",
        "bt_button": "Enable Bluetooth pairing",
        "bt_status": "BT status:",
        "bt_after": "Once paired you can play from <b>any app</b> on your phone (YouTube Music, podcasts, anything) — the audio goes to {{DEVICE}}.",
        "spotify_head": "Spotify",
        "spotify_1": "Open the <b>Spotify</b> app on your phone/PC.",
        "spotify_2": "Tap the devices icon (Spotify Connect) and pick <b>{{DEVICE}}</b>.",
        "spotify_note": "No pairing needed — works over the network.",
        "airplay_head": "AirPlay",
        "airplay_1": "On iPhone/iPad/Mac open Control Center or the AirPlay icon in your music app.",
        "airplay_2": "Pick <b>{{DEVICE}}</b> as the speaker.",
        "lms_head": "Radio / library (Lyrion Music Server)",
        "tidal_head": "TIDAL",
        "tidal_note": "TIDAL streams through Lyrion Music Server. Connect your account once — then pick music from Squeezer/iPeng or the LMS web UI.",
        "tidal_connect": "Connect TIDAL account",
        "tidal_link_note": "Open the link and sign in to TIDAL:",
        "tidal_waiting": "Waiting for sign-in…",
        "tidal_expired": "The link expired — try again.",
        "tidal_logged": "Signed in as",
        "tidal_forget": "Disconnect account",
        "tidal_forget_confirm": "Disconnect the TIDAL account? Sign in again anytime.",
        "tidal_show_note": "The switch only hides TIDAL on the main screen — it does not sign you out.",
        "tidal_missing": "The TIDAL plugin is not installed in LMS — re-run setup.sh to add it.",
        "lms_1": "Install the <b>Squeezer</b> app (Android) or <b>iPeng</b> (iOS) — that is the main remote.",
        "lms_2": "Pick the <b>{{PLAYER}}</b> player and play TIDAL, internet radio, playlists.",
        "lms_web": "Or from a browser:",
        "lms_web2": "(Material Skin).",
        "players_label": "Players:",
        # main page JS
        "js_pairing": "pairing: ",
        "js_ready": "ready",
        "js_off": "off",
        "js_connected": "connected: ",
        "js_silence": "Silence — nothing is playing.",
        "js_dac_hold": "open, silent",
        "js_dac_free": "Output free — any source can grab it.",
        "js_ctrl_hint": "control from the source app",
        "js_pair_active_pre": "Pairing active — look for \"{{DEVICE}}\" (",
        "js_pair_active_suf": "s)",
        # source states (sent via /api/status)
        "state_playing": "playing",
        "state_paused": "paused",
        "state_idle": "idle",
        "state_connected": "connected",
        # settings page
        "settings_head": "Settings",
        "back_to_panel": "← panel",
        "wifi_now_head": "Wi-Fi — current connection",
        "wifi_saved_head": "Saved networks",
        "wifi_saved_note": "The Pi automatically joins the first available network from this list (DietPi stores up to 5). Perfect for home + a second location.",
        "wifi_add_head": "Add a network",
        "wifi_add_note": "Type it in by hand (networks out of range work too — SSID must match exactly!) or pick one from a scan.",
        "wifi_ssid_ph": "Network name (SSID)",
        "wifi_key_ph": "Password (empty = open network)",
        "wifi_save_btn": "Save network",
        "wifi_scan_btn": "Scan for networks",
        "bts_head": "Bluetooth — paired devices",
        "bts_note": "Tap a device to connect it — no pairing mode needed. After boot the device also tries to reconnect to paired phones by itself.",
        "js_bt_none": "Nothing paired yet — use the pairing button on the main panel.",
        "js_bt_connecting": "Connecting…",
        "js_bt_disconnect": "disconnect",
        "bt_bad_mac": "Invalid device address.",
        "bt_conn_ok": "Connected.",
        "bt_conn_fail": "Could not connect (device off / out of range / Bluetooth disabled on the phone?).",
        "bt_disc_ok": "Disconnected.",
        "bts_debug_btn": "Audio/BT diagnostics",
        "bts_test_btn": "Test sound",
        "audio_test_btn": "Test the selected output",
        "bt_reconnect_label": "Auto-reconnect paired devices",
        "bt_reconnect_note": "After boot the device always retries for a short while. Turn this on to keep retrying at the interval below.",
        "bt_interval_label": "Retry interval (seconds)",
        "js_bt_testing": "Playing the test sound…",
        "audio_test_ok": "Test sound played on {dev} — the selected output works.",
        "audio_test_fail": "Test sound FAILED on „{dev}”: {err}",
        "viz_head": "Visualizer (HDMI)",
        "viz_note": "Bar style on the monitor. Changing it restarts the visualizer (music keeps playing). Tap ✎ to edit a preset (name + parameters); \"New preset\" adds one.",
        "viz_missing": "Not installed — re-run setup.sh (answer y to the visualizer question) or visualizer/install.sh; this card comes alive after that.",
        "viz_new_preset": "New preset",
        "viz_name_ph": "Preset name",
        "viz_save": "Save preset",
        "viz_delete": "Delete preset",
        "viz_edit_title": "Edit preset",
        "viz_name_bad": "The preset name must be 1-24 characters.",
        "viz_saved": "Preset „{label}” saved.",
        "viz_deleted": "Preset „{label}” deleted.",
        "viz_last": "Cannot delete the last preset.",
        "js_vdel_pre": "Delete preset \"",
        "js_vdel_suf": "\"?",
        "viz_p_framerate": "Framerate (fps)",
        "viz_p_bar_width": "Bar width",
        "viz_p_bar_spacing": "Bar spacing",
        "viz_p_noise": "Smoothing (higher = calmer, lower = snappier)",
        "viz_p_monstercat": "Monstercat smoothing (rounded peaks)",
        "viz_p_waves": "Waves smoothing (ripple falloff)",
        "viz_p_color": "Bar color",
        "viz_p_background": "Background",
        "viz_apply": "Apply",
        "viz_eng_cava": "Bars (cava)",
        "viz_eng_glsl": "Shaders (glslViewer)",
        "viz_engine_set": "Visualizer switched to {engine}.",
        "viz_edit": "Edit",
        "viz_scale_head": "Render scale",
        "viz_scale_note": "Lower = smoother on the Pi's GPU (renders at a fraction of the resolution, then upscales).",
        "viz_scale_set": "Render scale: {scale}×",
        "js_glsl_err": "Shader engine failed, showing cava instead. Reason: ",
        "viz_engine_bad": "Unknown engine.",
        "viz_glsl_missing": "glslViewer is not installed on the device (re-run the visualizer installer).",
        "shader_plasma": "Plasma",
        "shader_tunnel": "Tunnel",
        "shader_copper": "Copper bars",
        "shader_cube": "Cube",
        "shader_scope": "Oscilloscope",
        "shader_grid": "Grid",
        "shader_drop": "Drop a .frag file here (or tap to pick one). Uploading the same name updates the shader.",
        "shader_uploaded": "Shader „{name}” installed.",
        "shader_bad_name": "Bad shader file name — letters/digits/dashes plus .frag.",
        "shader_bad_src": "This does not look like a fragment shader (no void main / gl_FragColor).",
        "shader_too_big": "Shader too big (max 64 kB).",
        "shader_deleted": "Shader „{name}” removed.",
        "shader_del_active": "This shader is on screen right now — switch to another one first.",
        "sdel_title": "Remove shader",
        "js_sdel_pre": "Remove shader \"",
        "js_sdel_suf": "\"?",
        "audio_head": "Audio output",
        "audio_out_note": "Where the sound goes: the DAC HAT or the monitor over HDMI. A card that is up (green dot) switches live; a card that is off (red dot) is enabled in the boot config and needs a reboot.",
        "audio_hdmi_nodisp": "No monitor on the HDMI port — HDMI audio stays silent until a display is connected.",
        "upd_head": "Updates",
        "upd_note": "Fetches the latest Synchrofazotron from GitHub — the same as re-running setup.sh (safe, settings are kept). The check compares the installed panel with the repo.",
        "upd_check_btn": "Check for updates",
        "upd_run_btn": "Update now",
        "appupd_head": "Mobile app",
        "appupd_note": "Update the Android app to the latest build. The check compares the installed build with the latest release.",
        "appupd_version": "Installed",
        "appupd_run_btn": "Download & install",
        "appupd_available": "Update available — download it.",
        "appupd_current": "You have the latest version.",
        "appupd_downloading": "Downloading",
        "appupd_installing": "Downloaded — the system installer takes it from here.",
        "appupd_allow": "Allow this app to install updates on the screen that just opened, then tap again.",
        "appupd_dl_fail": "In-app download failed — opening the browser instead.",
        "exp_radiofx": "Smooth radio loading",
        "exp_radiofx_note": "Gentle slide-in and skeleton rows while station lists load (this device only).",
        "upd_started": "Update started.",
        "upd_already": "An update is already running.",
        "upd_fail": "Could not start the update.",
        "js_upd_checking": "Checking…",
        "js_upd_available": "A new version is available.",
        "js_upd_current": "Up to date.",
        "js_upd_checkfail": "Check failed (no network?).",
        "js_upd_confirm": "Update now? Takes a minute or two; the panel restarts briefly and players may blip.",
        "js_upd_running": "Updating… the panel may briefly disconnect — do not power off.",
        "js_upd_done": "Updated — reloading.",
        "js_upd_failed": "Update failed — check /var/log/synchrofazotron-setup.log on the device.",
        "name_head": "Device name",
        "name_note": "The name shown here, seen while pairing Bluetooth, and used for AirPlay / LMS. The hostname follows a simplified version (spaces become dashes).",
        "name_ph": "Device name",
        "name_save": "Save name",
        "name_bad": "The name must be 1-32 characters (no quotes or backslashes).",
        "name_set": "Renamed to {name}. The hostname and network address may change; some names refresh after a reboot.",
        "appearance_head": "Appearance & language",
        "lang_head": "Language",
        "lang_note": "Panel language. The choice is saved on the device.",
        "theme_head": "Theme",
        "theme_note": "Look of the panel. Saved in this browser (per device).",
        "theme_system": "System (auto)",
        "theme_neon": "Neon (legacy)",
        "theme_mono_light": "Mono — light",
        "theme_mono_dark": "Mono — dark",
        "reboot_head": "Reboot",
        "reboot_note": "Restart the device. Music stops for about a minute while it comes back up.",
        "how_head": "How it works",
        "how_note": "Networks go into the DietPi database (the same one <code>dietpi-config</code> uses) and the Wi-Fi configuration is reloaded on the fly — no reboot. Removing the network you are currently connected through is blocked so you cannot lock yourself out.",
        "about_head": "About",
        "about_note": "Synchrofazotron is a thin layer of glue — the heavy lifting is done by these excellent open-source projects and the wonderful people behind them:",
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
        "js_scanning": "Scanning… (a few seconds)",
        "js_scan_none": "Nothing found (the radio can be busy — try again).",
        "js_scan_fail": "Scan failed — try again.",
        "js_viz_stop": "⏻ Stop visualizer",
        "js_viz_start": "⏻ Start visualizer",
        "viz_hdmi_off": "HDMI not connected",
        "viz_hdmi_off_sub": "Plug a monitor into the HDMI port to see the visualizer.",
        "viz_off_hint": "Visualizer is off. Turn it on to pick a look.",
        "js_name_confirm": "Rename the device? The Bluetooth name changes and the network address (hostname) may change too — you might have to reconnect to reach the panel.",
        "js_audio_confirm": "Switch the audio output? The change needs a reboot.",
        "js_audio_reboot": "Config changed — reboot to apply.",
        "js_reboot": "Reboot the device",
        "js_reboot_confirm": "Reboot now? Music will stop for about a minute.",
        "js_rebooting": "Rebooting… the panel will come back in about a minute.",
        "reboot_done_toast": "Reboot finished",
        "upd_done_toast": "Update finished",
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
        "viz_params_set": "Custom settings applied.",
        "viz_stopped": "Visualizer turned off — it stays off until you switch it back on.",
        "viz_started": "Visualizer started.",
        "audio_bad": "Unknown output (expected dac or hdmi).",
        "audio_cfg_fail": "Could not read the boot config (config.txt).",
        "audio_set": "Output switched to {out} — reboot the device to apply.",
        "audio_set_live": "Output switched to {out} (live — no reboot).",
        "audio_card_absent": "{out} is not available — no such sound card is up.",
        "lang_set": "Language switched to English.",
    },
    "pl": {
        "title_panel": "panel",
        "title_settings": "ustawienia",
        "sub_panel": "Panel sterowania odtwarzaczem audio",
        "settings_link_title": "Ustawienia",
        "tab_now": "Teraz gra",
        "tab_viz": "Wizualizer",
        "tab_radio": "Radio",
        "radio_browse": "Przeglądaj",
        "radio_search": "Szukaj",
        "radio_fav": "Ulubione",
        "radio_search_ph": "Szukaj stacji, gatunków…",
        "radio_empty": "Nic tu nie ma.",
        "radio_fav_empty": "Brak ulubionych. Tapnij gwiazdkę przy stacji, żeby dodać.",
        "radio_loading": "Ładowanie…",
        "radio_added": "Dodano do ulubionych",
        "radio_removed": "Usunięto z ulubionych",
        "radio_play_err": "Nie udało się odtworzyć tej stacji",
        "radio_unavailable": "Lyrion Music Server jest nieosiągalny.",
        "st_wifi_off": "Brak sieci",
        "st_bt_ready": "Gotowy",
        "st_bt_off": "Wyłączony",
        "st_bt_pairing": "Parowanie…",
        "device_head": "Urządzenie",
        "device_connected": "Połączone urządzenie",
        "switch_device": "Zmień urządzenie",
        "pair_short": "Paruj",
        "wifi_none_short": "Wi-Fi",
        "wifi_header_title": "Wi-Fi — otwórz ustawienia sieci",
        "sheet_sources": "Źródła",
        "viz_more": "Edycja presetów i wgrywanie shaderów są w ustawieniach.",
        "how_connect_head": "Jak podłączyć źródła",
        "nav_customize": "Personalizacja",
        "nav_connections": "Połączenia",
        "vol_head": "Głośność",
        "vol_none": "Żadne źródło teraz nie gra.",
        "exp_head": "Eksperymentalne",
        "exp_note": "Tu mieszkają funkcje w budowie. Przydatne, ale mogą się zmienić lub kaprysić.",
        "exp_normalize": "Dostosuj normalizację wizualizera",
        "exp_normalize_note": "Wyłączone = domyślny auto-gain (żywy obraz przy "
                              "każdej głośności). Włączone = ręczne strojenie "
                              "każdego silnika.",
        "viz_normalize_on": "Normalizacja wizualizera: własne parametry zastosowane.",
        "viz_normalize_off": "Normalizacja wizualizera wróciła do domyślnej.",
        "norm_autosens": "Automatyczna czułość (autosens)",
        "norm_sensitivity": "Czułość",
        "norm_boost": "Maks. podbicie",
        "norm_target": "Poziom docelowy",
        "nav_config": "Konfiguracja",
        "nav_sources": "Źródła",
        "nav_viz": "Wizualizer",
        "nav_about": "O projekcie",
        "wifi_add_btn": "Dodaj sieć",
        "modal_cancel": "Anuluj",
        "ts_head": "Tailscale",
        "ts_note": "Połącz z Tailscale, żeby bezpiecznie zarządzać urządzeniem z dowolnego miejsca — panel działa bez otwierania portów.",
        "ts_missing": "Tailscale nie jest zainstalowany na urządzeniu.",
        "ts_up_ok": "Tailscale połączony.",
        "ts_down_ok": "Tailscale rozłączony.",
        "ts_login": "Tailscale wymaga jednorazowego logowania — odpal tailscale up na urządzeniu.",
        "ts_fail": "Polecenie tailscale nie powiodło się.",
        "src_not_installed": "niezainstalowane",
        "src_on_msg": "{name} włączone.",
        "src_off_msg": "{name} wyłączone.",
        "src_fail_msg": "Nie udało się przełączyć {name} — sprawdź kropki usług.",
        "src_disabled_hint": "Wyłączone — przełącz, żeby używać tego źródła.",
        "src_unknown": "Nieznane źródło.",
        "js_src_off_pre": "Wyłączyć ",
        "js_src_off_suf": "? Odtwarzanie z tego źródła się zatrzyma.",
        "bt_forget_title": "Zapomnij urządzenie",
        "js_bt_forget_pre": "Zapomnieć „",
        "js_bt_forget_suf": "”? Telefon będzie musiał sparować się od nowa.",
        "bt_forgot": "Urządzenie zapomniane.",
        "viz_studio_head": "Studio shaderów",
        "viz_studio_note": "Zaprojektuj własny shader w studiu w przeglądarce, a pobrany plik .frag upuść na kartę shaderów.",
        "viz_studio_btn": "Otwórz studio",
        "about_desc": "Synchrofazotron zamienia Raspberry Pi w odtwarzacz audio z wieloma źródłami: Bluetooth, AirPlay, Spotify Connect oraz TIDAL/radio/biblioteka przez Lyrion Music Server, do tego wizualizer muzyki na HDMI.",
        "about_repo": "Kod źródłowy, dokumentacja i zgłoszenia:",
        "about_license": "Wolne oprogramowanie na licencji GPL-3.0.",
        "about_version": "Wersja",
        "about_app_version": "Wersja aplikacji (Google Play)",
        "now_playing": "Teraz gra",
        "warn_multi": "Kilka źródeł gra jednocześnie — pierwsze zajmuje DAC, reszta gra w próżnię. Zatrzymaj niepotrzebne.",
        "bt_head": "Bluetooth",
        "bt_intro": "Kliknij, żeby urządzenie stało się widoczne i gotowe do sparowania przez <b>{{PAIR_WIN}} sekund</b>. Potem w telefonie: Bluetooth → wybierz <b>{{DEVICE}}</b>.",
        "bt_button": "Włącz parowanie Bluetooth",
        "bt_status": "Status BT:",
        "bt_after": "Po sparowaniu możesz grać z <b>dowolnej apki</b> na telefonie (YouTube Music, podcasty, cokolwiek) — dźwięk poleci na {{DEVICE}}.",
        "spotify_head": "Spotify",
        "spotify_1": "Otwórz apkę <b>Spotify</b> na telefonie/PC.",
        "spotify_2": "Dotknij ikony urządzeń (Spotify Connect) i wybierz <b>{{DEVICE}}</b>.",
        "spotify_note": "Nie trzeba nic parować — działa po sieci.",
        "airplay_head": "AirPlay",
        "airplay_1": "Na iPhone/iPad/Mac otwórz Centrum sterowania lub ikonę AirPlay w apce muzycznej.",
        "airplay_2": "Wybierz <b>{{DEVICE}}</b> jako głośnik.",
        "lms_head": "Radio / biblioteka (Lyrion Music Server)",
        "tidal_head": "TIDAL",
        "tidal_note": "TIDAL gra przez Lyrion Music Server. Połącz konto raz — potem wybieraj muzykę ze Squeezer/iPeng albo z webowego LMS.",
        "tidal_connect": "Połącz konto TIDAL",
        "tidal_link_note": "Otwórz link i zaloguj się w TIDAL:",
        "tidal_waiting": "Czekam na zalogowanie…",
        "tidal_expired": "Link wygasł — spróbuj ponownie.",
        "tidal_logged": "Zalogowano jako",
        "tidal_forget": "Odłącz konto",
        "tidal_forget_confirm": "Odłączyć konto TIDAL? Możesz zalogować się ponownie w każdej chwili.",
        "tidal_show_note": "Przełącznik tylko ukrywa TIDAL na głównej — nie wylogowuje.",
        "tidal_missing": "Wtyczka TIDAL nie jest zainstalowana w LMS — odpal ponownie setup.sh.",
        "lms_1": "Zainstaluj apkę <b>Squeezer</b> (Android) lub <b>iPeng</b> (iOS) — to główny pilot.",
        "lms_2": "Wybierz odtwarzacz <b>{{PLAYER}}</b> i graj TIDAL, radio internetowe, playlisty.",
        "lms_web": "Albo z przeglądarki:",
        "lms_web2": "(Material Skin).",
        "players_label": "Odtwarzacze:",
        "js_pairing": "parowanie: ",
        "js_ready": "gotowy",
        "js_off": "wyłączony",
        "js_connected": "połączone: ",
        "js_silence": "Cisza — nic nie gra.",
        "js_dac_hold": "otwarte, nie gra",
        "js_dac_free": "Wyjście wolne — każde źródło może je przejąć.",
        "js_ctrl_hint": "steruj z apki źródła",
        "js_pair_active_pre": "Parowanie aktywne — szukaj \"{{DEVICE}}\" (",
        "js_pair_active_suf": "s)",
        "state_playing": "gra",
        "state_paused": "pauza",
        "state_idle": "cisza",
        "state_connected": "połączony",
        "settings_head": "Ustawienia",
        "back_to_panel": "← panel",
        "wifi_now_head": "Wi-Fi — bieżące połączenie",
        "wifi_saved_head": "Zapisane sieci",
        "wifi_saved_note": "Pi łączy się automatycznie z pierwszą dostępną z tej listy (DietPi mieści maks. 5). Idealne na sieć domową + drugą lokalizację.",
        "wifi_add_head": "Dodaj sieć",
        "wifi_add_note": "Wpisz ręcznie (sieci spoza zasięgu też można — SSID co do znaku!) albo wybierz ze skanu.",
        "wifi_ssid_ph": "Nazwa sieci (SSID)",
        "wifi_key_ph": "Hasło (puste = sieć otwarta)",
        "wifi_save_btn": "Zapisz sieć",
        "wifi_scan_btn": "Skanuj otoczenie",
        "bts_head": "Bluetooth — sparowane urządzenia",
        "bts_note": "Kliknij urządzenie, żeby je połączyć — bez trybu parowania. Po starcie urządzenie samo próbuje też wznowić połączenie ze sparowanymi telefonami.",
        "js_bt_none": "Nic jeszcze nie sparowano — użyj przycisku parowania na głównym panelu.",
        "js_bt_connecting": "Łączę…",
        "js_bt_disconnect": "rozłącz",
        "bt_bad_mac": "Nieprawidłowy adres urządzenia.",
        "bt_conn_ok": "Połączono.",
        "bt_conn_fail": "Nie udało się połączyć (urządzenie wyłączone / poza zasięgiem / Bluetooth w telefonie wyłączony?).",
        "bt_disc_ok": "Rozłączono.",
        "bts_debug_btn": "Diagnostyka audio/BT",
        "bts_test_btn": "Test dźwięku",
        "audio_test_btn": "Testuj wybrane wyjście",
        "bt_reconnect_label": "Auto-reconnect sparowanych",
        "bt_reconnect_note": "Po starcie urządzenie i tak przez chwilę ponawia próby. Włącz, żeby ponawiać dalej co zadany czas.",
        "bt_interval_label": "Odstęp prób (sekundy)",
        "js_bt_testing": "Gram dźwięk testowy…",
        "audio_test_ok": "Dźwięk testowy zagrany na {dev} — wybrane wyjście działa.",
        "audio_test_fail": "Test na „{dev}” NIE przeszedł: {err}",
        "viz_head": "Wizualizer (HDMI)",
        "viz_note": "Styl słupków na monitorze. Zmiana restartuje wizualizer (muzyka gra dalej). Kliknij ✎, żeby edytować preset (nazwa + parametry); „Nowy preset” dodaje kolejny.",
        "viz_missing": "Niezainstalowany — odpal ponownie setup.sh (odpowiedz y na pytanie o wizualizer) albo visualizer/install.sh; karta ożyje po instalacji.",
        "viz_new_preset": "Nowy preset",
        "viz_name_ph": "Nazwa presetu",
        "viz_save": "Zapisz preset",
        "viz_delete": "Usuń preset",
        "viz_edit_title": "Edycja presetu",
        "viz_name_bad": "Nazwa presetu: 1-24 znaki.",
        "viz_saved": "Preset „{label}” zapisany.",
        "viz_deleted": "Preset „{label}” usunięty.",
        "viz_last": "Nie można usunąć ostatniego presetu.",
        "js_vdel_pre": "Usunąć preset „",
        "js_vdel_suf": "”?",
        "viz_p_framerate": "Klatki (fps)",
        "viz_p_bar_width": "Szerokość słupka",
        "viz_p_bar_spacing": "Odstęp słupków",
        "viz_p_noise": "Wygładzanie (więcej = spokojniej, mniej = żwawiej)",
        "viz_p_monstercat": "Wygładzanie Monstercat (zaokrąglone szczyty)",
        "viz_p_waves": "Wygładzanie Waves (falujące opadanie)",
        "viz_p_color": "Kolor słupków",
        "viz_p_background": "Tło",
        "viz_apply": "Zastosuj",
        "viz_eng_cava": "Słupki (cava)",
        "viz_eng_glsl": "Shadery (glslViewer)",
        "viz_engine_set": "Wizualizer przełączony na {engine}.",
        "viz_edit": "Edytuj",
        "viz_scale_head": "Skala renderowania",
        "viz_scale_note": "Niżej = płynniej na GPU Pi (renderuje w ułamku rozdzielczości, potem skaluje w górę).",
        "viz_scale_set": "Skala renderowania: {scale}×",
        "js_glsl_err": "Silnik shaderów nie wystartował, gra cava. Powód: ",
        "viz_engine_bad": "Nieznany silnik.",
        "viz_glsl_missing": "glslViewer nie jest zainstalowany na urządzeniu (odpal ponownie instalator wizualizera).",
        "shader_plasma": "Plazma",
        "shader_tunnel": "Tunel",
        "shader_copper": "Paski copper",
        "shader_cube": "Kostka",
        "shader_scope": "Oscyloskop",
        "shader_grid": "Siatka",
        "shader_drop": "Upuść tu plik .frag (albo kliknij i wybierz). Ta sama nazwa = aktualizacja shadera.",
        "shader_uploaded": "Shader „{name}” zainstalowany.",
        "shader_bad_name": "Zła nazwa pliku — litery/cyfry/myślniki plus .frag.",
        "shader_bad_src": "To nie wygląda na fragment shader (brak void main / gl_FragColor).",
        "shader_too_big": "Shader za duży (maks. 64 kB).",
        "shader_deleted": "Shader „{name}” usunięty.",
        "shader_del_active": "Ten shader właśnie gra na ekranie — najpierw przełącz na inny.",
        "sdel_title": "Usuń shader",
        "js_sdel_pre": "Usunąć shader „",
        "js_sdel_suf": "”?",
        "audio_head": "Wyjście dźwięku",
        "audio_out_note": "Którędy wychodzi dźwięk: DAC (nakładka HAT) albo monitor po HDMI. Karta dostępna (zielona kropka) przełącza się od razu; kartę wyłączoną (czerwona kropka) włącza konfiguracja startowa i wymaga restartu.",
        "audio_hdmi_nodisp": "Brak monitora na porcie HDMI — dźwięk HDMI będzie cichy, dopóki nie podłączysz ekranu.",
        "upd_head": "Aktualizacje",
        "upd_note": "Pobiera najnowszy Synchrofazotron z GitHuba — to samo co ponowne setup.sh (bezpieczne, ustawienia zostają). Sprawdzenie porównuje zainstalowany panel z repo.",
        "upd_check_btn": "Sprawdź aktualizacje",
        "upd_run_btn": "Aktualizuj",
        "appupd_head": "Aplikacja mobilna",
        "appupd_note": "Zaktualizuj aplikację Android do najnowszej wersji. Sprawdzenie porównuje zainstalowaną wersję z najnowszym wydaniem.",
        "appupd_version": "Zainstalowana",
        "appupd_run_btn": "Pobierz i zainstaluj",
        "appupd_available": "Dostępna aktualizacja — pobierz.",
        "appupd_current": "Masz najnowszą wersję.",
        "appupd_downloading": "Pobieranie",
        "appupd_installing": "Pobrane — resztę robi systemowy instalator.",
        "appupd_allow": "Zezwól aplikacji na instalowanie aktualizacji na ekranie, który się otworzył, i kliknij ponownie.",
        "appupd_dl_fail": "Pobieranie w aplikacji nie powiodło się — otwieram przeglądarkę.",
        "exp_radiofx": "Płynne ładowanie radia",
        "exp_radiofx_note": "Delikatny slide-in i szkielety wierszy podczas ładowania list stacji (tylko to urządzenie).",
        "upd_started": "Aktualizacja wystartowała.",
        "upd_already": "Aktualizacja już trwa.",
        "upd_fail": "Nie udało się wystartować aktualizacji.",
        "js_upd_checking": "Sprawdzam…",
        "js_upd_available": "Jest nowsza wersja.",
        "js_upd_current": "Wersja aktualna.",
        "js_upd_checkfail": "Nie udało się sprawdzić (brak sieci?).",
        "js_upd_confirm": "Zaktualizować teraz? Potrwa minutę–dwie; panel na chwilę się zrestartuje, odtwarzacze mogą mrugnąć.",
        "js_upd_running": "Aktualizuję… panel może na moment zniknąć — nie wyłączaj zasilania.",
        "js_upd_done": "Zaktualizowane — przeładowuję.",
        "js_upd_failed": "Aktualizacja nie wyszła — zajrzyj do /var/log/synchrofazotron-setup.log na urządzeniu.",
        "name_head": "Nazwa urządzenia",
        "name_note": "Nazwa pokazywana tutaj, widoczna przy parowaniu Bluetooth oraz używana dla AirPlay / LMS. Hostname przyjmuje uproszczoną wersję (spacje zamieniane na myślniki).",
        "name_ph": "Nazwa urządzenia",
        "name_save": "Zapisz nazwę",
        "name_bad": "Nazwa musi mieć 1-32 znaki (bez cudzysłowów i backslashy).",
        "name_set": "Zmieniono nazwę na {name}. Hostname i adres w sieci mogą się zmienić; część nazw odświeży się po restarcie.",
        "appearance_head": "Wygląd i język",
        "lang_head": "Język",
        "lang_note": "Język panelu. Wybór zapisuje się na urządzeniu.",
        "theme_head": "Motyw",
        "theme_note": "Wygląd panelu. Zapisywany w tej przeglądarce (per urządzenie).",
        "theme_system": "Systemowy (auto)",
        "theme_neon": "Neon (przestarzały)",
        "theme_mono_light": "Mono — jasny",
        "theme_mono_dark": "Mono — ciemny",
        "reboot_head": "Restart",
        "reboot_note": "Zrestartuj urządzenie. Muzyka przestanie grać na około minutę, aż wróci.",
        "how_head": "Jak to działa",
        "how_note": "Sieci trafiają do bazy DietPi (tej samej, którą widzi <code>dietpi-config</code>), a konfiguracja Wi-Fi jest przeładowywana w locie — bez restartu. Usunięcie sieci, przez którą aktualnie jesteś połączony, jest zablokowane, żeby nie odciąć sobie dostępu.",
        "about_head": "O projekcie",
        "about_note": "Synchrofazotron to cienka warstwa kleju — całą ciężką robotę odwalają te świetne projekty open source i wspaniali ludzie, którzy za nimi stoją:",
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
        "js_scanning": "Skanuję… (kilka sekund)",
        "js_scan_none": "Nic nie znaleziono (radio bywa zajęte — spróbuj ponownie).",
        "js_scan_fail": "Skan nie wyszedł — spróbuj ponownie.",
        "js_viz_stop": "⏻ Zatrzymaj wizualizer",
        "js_viz_start": "⏻ Uruchom wizualizer",
        "viz_hdmi_off": "HDMI niepodłączone",
        "viz_hdmi_off_sub": "Podłącz monitor do portu HDMI, żeby zobaczyć wizualizer.",
        "viz_off_hint": "Wizualizer jest wyłączony. Włącz go, żeby wybrać wygląd.",
        "js_name_confirm": "Zmienić nazwę urządzenia? Zmieni się nazwa Bluetooth, a adres w sieci (hostname) też może się zmienić — może być trzeba połączyć się ponownie, żeby wejść do panelu.",
        "js_audio_confirm": "Przełączyć wyjście dźwięku? Zmiana wymaga restartu.",
        "js_audio_reboot": "Konfiguracja zmieniona — zrestartuj, żeby zadziałało.",
        "js_reboot": "Zrestartuj urządzenie",
        "js_reboot_confirm": "Zrestartować teraz? Muzyka przestanie grać na około minutę.",
        "js_rebooting": "Restartuję… panel wróci za około minutę.",
        "reboot_done_toast": "Restart zakończony",
        "upd_done_toast": "Aktualizacja zakończona",
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
        "viz_params_set": "Własne ustawienia zastosowane.",
        "viz_stopped": "Wizualizer wyłączony — pozostanie wyłączony, dopóki go nie włączysz.",
        "viz_started": "Wizualizer wystartowany.",
        "audio_bad": "Nieznane wyjście (oczekiwane dac lub hdmi).",
        "audio_cfg_fail": "Nie udało się odczytać konfiguracji startowej (config.txt).",
        "audio_set": "Wyjście przełączone na {out} — zrestartuj urządzenie, żeby zadziałało.",
        "audio_set_live": "Wyjście przełączone na {out} (na żywo — bez restartu).",
        "audio_card_absent": "{out} niedostępne — nie ma takiej karty dźwiękowej.",
        "lang_set": "Przełączono na polski.",
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
    if DEV_MODE:
        return ""   # sandbox: never touch the host while previewing locally
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"__err__ {e}"


def _bt_show():
    return _run(["bluetoothctl", "show"])


def _parse_devices(out):
    devices = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 3 and parts[0] == "Device":
            devices.append((parts[1], parts[2]))
    return devices


def _connected_devices():
    """Returns a list [(mac, name)] of connected BT devices."""
    return _parse_devices(_run(["bluetoothctl", "devices", "Connected"]))


def _paired_devices():
    """[(mac, name)] of paired devices (old bluez spells the command differently)."""
    devices = _parse_devices(_run(["bluetoothctl", "devices", "Paired"]))
    return devices or _parse_devices(_run(["bluetoothctl", "paired-devices"]))


def _bt_payload():
    connected = {m for m, _ in _connected_devices()}
    return {"paired": [{"mac": m, "name": n, "connected": m in connected}
                       for m, n in _paired_devices()],
            "reconnect": _bt_reconnect_cfg()}


_MAC_RE = re.compile(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}")


def _bt_connect(mac):
    """Connects an already-paired device (no pairing mode needed)."""
    if not _MAC_RE.fullmatch(mac):
        return False, T("bt_bad_mac")
    _run(["bluetoothctl", "power", "on"])
    out = _run(["bluetoothctl", "connect", mac], timeout=25)
    if "Connection successful" in out:
        return True, T("bt_conn_ok")
    return False, T("bt_conn_fail")


def _bt_disconnect(mac):
    if not _MAC_RE.fullmatch(mac):
        return False, T("bt_bad_mac")
    out = _run(["bluetoothctl", "disconnect", mac], timeout=15)
    return "__err__" not in out and "Failed" not in out, T("bt_disc_ok")


def _bt_forget(mac):
    """Removes the pairing entirely (the phone must pair again)."""
    if not _MAC_RE.fullmatch(mac):
        return False, T("bt_bad_mac")
    out = _run(["bluetoothctl", "remove", mac], timeout=10)
    _trusted.discard(mac)
    return "__err__" not in out and "Failed" not in out, T("bt_forgot")


def _aplay_device():
    """The ALSA device bluealsa-aplay is configured to play to."""
    m = re.search(r"bluealsa-aplay .*?(?:--pcm=|-d +)(\S+)",
                  _file_read(BLUEALSA_OVERRIDE))
    return m.group(1) if m else "default"


def _bt_debug():
    """Plain-text report answering 'BT is connected but silent — why?'."""
    lines = []
    dev = _aplay_device()
    lines.append(f"bluealsa-aplay output device: {dev}")
    lines.append("services: bluealsa=%s  bluealsa-aplay=%s  bluetooth=%s" % (
        _run(["systemctl", "is-active", "bluealsa"]),
        _run(["systemctl", "is-active", "bluealsa-aplay"]),
        _run(["systemctl", "is-active", "bluetooth"])))

    lines.append("")
    lines.append("--- BlueALSA PCMs (BT audio transports) ---")
    pcms = _run(["bluealsa-cli", "list-pcms"])
    lines.append(pcms.strip() or "(none — is the phone connected?)")
    for path in pcms.splitlines():
        path = path.strip()
        if "a2dp" in path:
            info = _run(["bluealsa-cli", "info", path])
            keep = [ln for ln in info.splitlines()
                    if re.match(r"\s*(Transport|Running|Format|Sampling|Channels)", ln)]
            lines.append(f"{path}:")
            lines.extend("  " + ln.strip() for ln in keep)

    lines.append("")
    lines.append("--- sound cards (/proc/asound/cards) ---")
    cards = _file_read("/proc/asound/cards")
    lines.append(cards.strip() or "(empty!)")

    lines.append("")
    lines.append("--- open playback streams ---")
    owners = _dac_owners()
    if owners:
        lines.extend(f"{o['label']}: " + ("PLAYING" if o["running"] else "open, silent (blocks a 1-substream device)")
                     for o in owners)
    else:
        lines.append("(nothing holds the output)")

    # audio-out bridge: alsaloop copies the loopback tap to the real card;
    # if it is down, everything through 'pistream' is silent (BT included)
    mode, bcard = _aout_read()
    bstate = _run(["systemctl", "is-active", AOUT_SERVICE])
    bcard_ok = bcard and bcard in cards
    lines.append("")
    lines.append(f"audio-out bridge (pistream-aout): {bstate}  "
                 f"{mode or '?'} -> plughw:{bcard or '?'} "
                 + ("(card present)" if bcard_ok else
                    "(CARD ABSENT/blank -> no sound reaches the output; "
                    "pick an available output in the panel)"))

    lines.append("")
    lines.append("--- bluealsa-aplay journal (last 15 lines) ---")
    lines.append(_run(["journalctl", "-u", "bluealsa-aplay", "-n", "15",
                       "--no-pager", "-o", "cat"], timeout=10).strip() or "(empty)")
    return {"report": "\n".join(lines), "device": dev}


def _audio_test():
    """Plays the standard test wav on the currently selected output card. The
    card is single-substream and normally held by the audio-out bridge, so we
    briefly stop the bridge to borrow the card, play, then resume it — this
    works even while a source (LMS/BT) is holding 'pistream'. Returns
    (ok, message)."""
    if DEV_MODE:
        return False, "sandbox mode — audio test disabled"
    mode = _audio_selected()
    cid = _dac_card_id() if mode == "dac" else _hdmi_card_id()
    if not cid:
        return False, T("audio_card_absent").format(out=mode.upper())
    dev = f"plughw:CARD={cid}"
    bridge_was = _service_active(AOUT_SERVICE)
    if bridge_was:
        _run(["systemctl", "stop", AOUT_SERVICE])   # free the card for the test
    try:
        r = subprocess.run(
            ["aplay", "-D", dev, "/usr/share/sounds/alsa/Front_Center.wav"],
            capture_output=True, text=True, timeout=15)
        rc, err = r.returncode, (r.stderr or "").strip()[:200]
    except Exception as e:  # noqa: BLE001
        rc, err = 1, str(e)
    finally:
        if bridge_was:
            _run(["systemctl", "start", AOUT_SERVICE])
    if rc == 0:
        return True, T("audio_test_ok").format(dev=dev)
    return False, T("audio_test_fail").format(dev=dev, err=err)


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


# Reconnecting after boot: phones do not always reconnect to an A2DP sink on
# their own, so like a real speaker the Pi pages the paired devices itself
# (connectable, NOT discoverable/pairable — pairing stays behind the panel
# button). Two phases: a short aggressive BURST right after start (always on),
# then optional periodic retries gated by a panel toggle (default off).
BT_AUTOCONNECT = os.environ.get("PISTREAM_BT_AUTOCONNECT", "1") == "1"
BT_BURST_WINDOW = 120       # aggressive reconnect window after start (seconds)
BT_BURST_INTERVAL = 10      # retry every 10 s during the burst
BT_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "bt-reconnect.json")


def _bt_reconnect_cfg():
    """Persisted periodic-reconnect setting: {'enabled': bool, 'interval': int}."""
    try:
        d = json.load(open(BT_CFG_FILE, encoding="utf-8"))
        return {"enabled": bool(d.get("enabled")),
                "interval": max(10, min(600, int(d.get("interval", 45))))}
    except Exception:  # noqa: BLE001
        return {"enabled": False, "interval": 45}


def _bt_reconnect_set(enabled, interval):
    try:
        interval = max(10, min(600, int(interval)))
    except (TypeError, ValueError):
        interval = 45
    cfg = {"enabled": bool(enabled), "interval": interval}
    _file_write(BT_CFG_FILE, json.dumps(cfg) + "\n")
    return cfg


def _bt_autoconnect_loop():
    start = time.time()
    while True:
        interval = 30
        try:
            cfg = _bt_reconnect_cfg()
            in_burst = (time.time() - start) < BT_BURST_WINDOW
            if in_burst or cfg["enabled"]:
                if _pair_seconds_left() == 0:  # keep out of an open pairing window
                    if "Powered: yes" not in _bt_show():
                        _run(["bluetoothctl", "power", "on"])
                    if not _connected_devices():
                        for mac, _name in _paired_devices():
                            _run(["bluetoothctl", "connect", mac], timeout=15)
                            if _connected_devices():
                                break
                interval = BT_BURST_INTERVAL if in_burst else cfg["interval"]
        except Exception:  # noqa: BLE001
            pass
        time.sleep(interval)


def _pair_seconds_left():
    left = int(_pair_deadline - time.time())
    return left if left > 0 else 0


def _service_active(name):
    return _run(["systemctl", "is-active", name]) == "active"


# ---------------------------------------------------------------------------
# Source features (settings page) — each source is a group of systemd units
# that can be switched off entirely (now AND at boot: disable --now) when
# somebody does not want e.g. AirPlay or Bluetooth on their device.
# ---------------------------------------------------------------------------
SOURCE_GROUPS = (
    {"id": "bluetooth", "label": "Bluetooth",
     "services": ("bluetooth", "bluealsa", "bluealsa-aplay")},
    {"id": "airplay", "label": "AirPlay", "services": ("shairport-sync",)},
    {"id": "lms", "label": "LMS", "services": ("lyrionmusicserver", "squeezelite")},
    {"id": "spotify", "label": "Spotify", "services": ("raspotify",)},
)


def _unit_state(name):
    enabled = _run(["systemctl", "is-enabled", name])
    return {"name": name,
            "installed": bool(enabled) and "__err__" not in enabled
            and "not-found" not in enabled,
            "enabled": enabled == "enabled",
            "active": _service_active(name)}


def _sources_payload():
    groups = []
    for g in SOURCE_GROUPS:
        if g["id"] == "spotify" and not SHOW_SPOTIFY:
            continue
        svcs = [_unit_state(s) for s in g["services"]]
        installed = all(s["installed"] for s in svcs)
        groups.append({"id": g["id"], "label": g["label"], "installed": installed,
                       "enabled": installed and all(s["active"] for s in svcs),
                       "services": svcs})
    return {"sources": groups}


def _source_toggle(sid, enable):
    g = next((x for x in SOURCE_GROUPS if x["id"] == sid), None)
    if not g:
        return False, T("src_unknown")
    verb = "enable" if enable else "disable"
    for s in g["services"]:
        _run(["systemctl", verb, "--now", s], timeout=25)
    if not all(_service_active(s) == enable for s in g["services"]):
        return False, T("src_fail_msg").format(name=g["label"])
    return True, T("src_on_msg" if enable else "src_off_msg").format(name=g["label"])


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


def _wifi_ssid():
    """Just the connected SSID (light — one iw call), '' if not connected.
    Used by the header badge which polls /api/status every few seconds."""
    m = re.search(r"^\s*SSID:\s*(.+)$", _run(["iw", "dev", WIFI_IFACE, "link"]), re.M)
    return m.group(1).strip() if m else ""


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


def _tailscale_state():
    """Presence + backend state for the settings toggle."""
    if not shutil.which("tailscale"):
        return {"installed": False, "active": False, "ip": ""}
    out = _run(["tailscale", "status", "--json"], timeout=8)
    active = re.search(r'"BackendState":\s*"Running"', out) is not None
    return {"installed": True, "active": active,
            "ip": _tailscale_ip() if active else ""}


def _tailscale_set(up):
    """(ok, message) — tailscale up/down. Going up may need a one-time
    login done on the device itself; the panel just reports that."""
    if not shutil.which("tailscale"):
        return False, T("ts_missing")
    if up:
        _run(["tailscale", "up", "--timeout=15s"], timeout=25)
        if _tailscale_state()["active"]:
            return True, T("ts_up_ok")
        return False, T("ts_login")
    out = _run(["tailscale", "down"], timeout=15)
    if "__err__" in out:
        return False, T("ts_fail")
    return True, T("ts_down_ok")


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
# The seed config is the first built-in preset (Snappy); install.sh only writes
# it on a fresh install, so a user's chosen/edited preset survives updates.
# ---------------------------------------------------------------------------
VIZ_CONF = "/opt/pistream-visualizer/cava.conf"
VIZ_SERVICE = "pistream-visualizer"
# Second engine: glslViewer shaders (viz-run.sh dispatches on the engine file).
VIZ_ENGINE_FILE = "/opt/pistream-visualizer/engine"
VIZ_GLSL_DIR = "/opt/pistream-visualizer/glsl"
VIZ_GLSL_ERR = "/opt/pistream-visualizer/glsl-error"
# glsl render scale (viz-run.sh -> viz-glsl VIZ_SCALE): lower = fewer fragments
# = higher fps on the Pi GPU. One of VIZ_SCALES; "1" = native.
VIZ_SCALE_FILE = "/opt/pistream-visualizer/scale"
VIZ_SCALES = ("1", "0.75", "0.5", "0.25")
# Experimental: "customize visualizer normalization". Both engines normalize
# the input level so the picture stays lively regardless of playback volume
# (players attenuate before the tee, so the viz tap is as quiet as the
# speakers). Off == the shipped defaults below; on == the user's parameters.
# Stored as JSON {"custom": bool, "cava": {...}, "glsl": {...}} — the glsl
# bridge reads the file itself, cava gets its values written into cava.conf.
# Legacy file contents ("0"/"1" from the old on/off toggle) read as not custom.
VIZ_NORMALIZE_FILE = "/opt/pistream-visualizer/normalize"
VIZ_NORM_DEFAULTS = {"cava": {"autosens": True, "sensitivity": 100},
                     "glsl": {"max_boost": 45, "target": 0.9}}
# Manual off-switch. When this flag exists the visualizer stays off even with a
# monitor attached — hdmi-watch.sh honours it instead of auto-starting. It is
# the user's intent (the panel toggle); the service's live state can differ
# (e.g. enabled but no HDMI = intent on, service off).
VIZ_DISABLED_FLAG = "/opt/pistream-visualizer/disabled"

_VIZ_TEMPLATE = """# preset: {name} (managed by the Synchrofazotron panel — /settings page)
[general]
framerate = {framerate}
autosens = {autosens}
sensitivity = {sensitivity}
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
background = {background}
foreground = {color}

[smoothing]
{smoothing}
"""

# Built-in preset defaults. Ids and labels are stable (proper names, same in
# every language) — until the user customizes presets, from then on the whole
# set lives in presets.json and this dict is only the fallback for a
# missing/corrupt file.
_VIZ_PARAM_KEYS = ("framerate", "bar_width", "bar_spacing",
                   "noise_reduction", "monstercat", "waves", "color", "background")
VIZ_PRESETS = {
    "snappy": {"label": "Snappy", "framerate": 60, "bar_width": 1,
               "bar_spacing": 1, "noise_reduction": 10, "monstercat": False,
               "waves": False, "color": "white", "background": "black"},
    "jumpy": {"label": "Jumpy", "framerate": 60, "bar_width": 8,
              "bar_spacing": 1, "noise_reduction": 50, "monstercat": False,
              "waves": False, "color": "cyan", "background": "black"},
    "smooth": {"label": "Smooth", "framerate": 40, "bar_width": 12,
               "bar_spacing": 2, "noise_reduction": 70, "monstercat": False,
               "waves": True, "color": "green", "background": "black"},
    "hot": {"label": "Hot", "framerate": 60, "bar_width": 1,
            "bar_spacing": 4, "noise_reduction": 10, "monstercat": True,
            "waves": False, "color": "yellow", "background": "black"},
}
VIZ_USER_PRESETS = "/opt/pistream-visualizer/presets.json"
# Pre-rename ids (Polish) still found in configs written by older panels.
_VIZ_LEGACY_IDS = {"klasyk": "classic", "gesty": "dense",
                   "fale": "waves", "masyw": "massive"}

# cava runs on the Linux text console (tty1, TERM=linux, noncurses output),
# whose palette is the 8 named ANSI colours — hex/truecolour is not honoured
# there (that needs cava's SDL output). Both bars and background pick from this
# full set, black included (black bars only make sense over a lit background).
VIZ_COLORS = ("cyan", "green", "blue", "magenta", "red", "yellow", "white", "black")
VIZ_BG_COLORS = VIZ_COLORS


def _viz_params():
    """Current cava parameters (parsed from the config the panel writes)."""
    txt = ""
    try:
        txt = open(VIZ_CONF, encoding="utf-8").read()
    except OSError:
        pass

    def num(key, default):
        m = re.search(rf"^{key} = (\d+)", txt, re.M)
        return int(m.group(1)) if m else default

    m = re.search(r"^foreground = (\S+)", txt, re.M)
    bg = re.search(r"^background = (\S+)", txt, re.M)
    return {"framerate": num("framerate", 45),
            "bar_width": num("bar_width", 9),
            "bar_spacing": num("bar_spacing", 2),
            "noise_reduction": num("noise_reduction", 10),
            "monstercat": bool(re.search(r"^monstercat = 1", txt, re.M)),
            "waves": bool(re.search(r"^waves = 1", txt, re.M)),
            "color": m.group(1) if m and m.group(1) in VIZ_COLORS else "magenta",
            "background": bg.group(1) if bg and bg.group(1) in VIZ_BG_COLORS else "black",
            "colors": list(VIZ_COLORS),
            "bg_colors": list(VIZ_BG_COLORS)}


def _viz_glsl_bin():
    return shutil.which("glslViewer") or shutil.which("glslviewer")


VIZ_GLSL_RUNNER = "/opt/pistream-visualizer/glsl-run.py"
_glsl_runner_ok = None


def _viz_glsl_ok():
    """The glsl engine works via the glslViewer binary OR the pygame runner."""
    global _glsl_runner_ok
    if _viz_glsl_bin():
        return True
    if _glsl_runner_ok is None:
        try:
            _glsl_runner_ok = bool(
                os.path.isfile(VIZ_GLSL_RUNNER)
                and subprocess.run(
                    ["python3", "-c", "import pygame, OpenGL, numpy"],
                    capture_output=True, timeout=20).returncode == 0)
        except Exception:  # noqa: BLE001
            _glsl_runner_ok = False
    return _glsl_runner_ok


def _viz_shaders():
    # Names starting with "_" are hidden (e.g. the update easter-egg shader).
    return sorted(n for n in (os.path.splitext(os.path.basename(f))[0]
                              for f in glob.glob(os.path.join(VIZ_GLSL_DIR, "*.frag")))
                  if not n.startswith("_"))


def _viz_engine():
    """(engine, shader) from the engine file; defaults to ('cava', 'plasma')."""
    try:
        parts = open(VIZ_ENGINE_FILE, encoding="utf-8").read().split()
    except OSError:
        parts = []
    engine = parts[0] if parts and parts[0] in ("cava", "glsl") else "cava"
    shader = parts[1] if len(parts) > 1 else "plasma"
    return engine, shader


def _viz_scale():
    """Current glsl render scale as a string ('1' when unset/native)."""
    v = _file_read(VIZ_SCALE_FILE).strip()
    return v if v in VIZ_SCALES else "1"


def _viz_set_scale(scale):
    """(ok, message). Sets the glsl render scale and restarts the visualizer."""
    if scale not in VIZ_SCALES:
        return False, T("viz_engine_bad")
    _file_write(VIZ_SCALE_FILE, scale + "\n")
    _run(["systemctl", "try-restart", VIZ_SERVICE])
    return True, T("viz_scale_set").format(scale=scale)


def _viz_norm_clamp(body):
    """Sanitized normalization settings from a JSON body (or the stored file)."""
    def num(sect, key, lo, hi, cast=int):
        try:
            v = cast((body.get(sect) or {}).get(key, VIZ_NORM_DEFAULTS[sect][key]))
        except (TypeError, ValueError):
            v = VIZ_NORM_DEFAULTS[sect][key]
        return max(lo, min(hi, v))

    autosens = (body.get("cava") or {}).get(
        "autosens", VIZ_NORM_DEFAULTS["cava"]["autosens"])
    return {"custom": bool(body.get("custom")),
            "cava": {"autosens": bool(autosens),
                     "sensitivity": num("cava", "sensitivity", 10, 500)},
            "glsl": {"max_boost": num("glsl", "max_boost", 1, 100),
                     "target": round(num("glsl", "target", 0.1, 1.0, float), 2)}}


def _viz_norm():
    """Normalization settings {"custom", "cava", "glsl"}. A missing file and
    legacy "0"/"1" contents (the old on/off toggle) both mean not customized."""
    try:
        cfg = json.loads(_file_read(VIZ_NORMALIZE_FILE) or "{}")
    except ValueError:
        cfg = {}
    return _viz_norm_clamp(cfg if isinstance(cfg, dict) else {})


def _viz_norm_cava():
    """Effective cava normalization values (defaults unless customized)."""
    norm = _viz_norm()
    return norm["cava"] if norm["custom"] else VIZ_NORM_DEFAULTS["cava"]


def _viz_set_normalize(body):
    """(ok, message). "Customize normalization": off = the shipped defaults,
    on = the user's per-engine parameters. The glsl bridge reads the JSON file
    itself; cava's autosens/sensitivity are patched into the live conf.
    Restart applies it (music keeps playing)."""
    norm = _viz_norm_clamp(body)
    _file_write(VIZ_NORMALIZE_FILE, json.dumps(norm) + "\n")
    cava = norm["cava"] if norm["custom"] else VIZ_NORM_DEFAULTS["cava"]
    try:
        conf = _file_read(VIZ_CONF)
        if conf:
            conf = re.sub(r"(?m)^autosens = .*$",
                          f"autosens = {1 if cava['autosens'] else 0}", conf)
            line = f"sensitivity = {cava['sensitivity']}"
            if re.search(r"(?m)^sensitivity = ", conf):
                conf = re.sub(r"(?m)^sensitivity = .*$", line, conf)
            else:  # confs written before the panel knew about sensitivity
                conf = conf.replace("[general]", f"[general]\n{line}", 1)
            _file_write(VIZ_CONF, conf)
    except Exception:  # noqa: BLE001
        pass
    _run(["systemctl", "try-restart", VIZ_SERVICE])
    return True, T("viz_normalize_on" if norm["custom"] else "viz_normalize_off")


def _shader_label(sid):
    label = T(f"shader_{sid}")
    return sid.capitalize() if label == f"shader_{sid}" else label


def _viz_clamp_params(body):
    """Sanitized cava parameters from a JSON body (editor and presets)."""
    def clamp(key, lo, hi, default):
        try:
            v = int(body.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    color = str(body.get("color", "magenta"))
    background = str(body.get("background", "black"))
    return {"framerate": clamp("framerate", 10, 120, 45),
            "bar_width": clamp("bar_width", 1, 20, 9),
            "bar_spacing": clamp("bar_spacing", 0, 10, 2),
            "noise_reduction": clamp("noise_reduction", 0, 100, 10),
            "monstercat": bool(body.get("monstercat")),
            "waves": bool(body.get("waves")),
            "color": color if color in VIZ_COLORS else "magenta",
            "background": background if background in VIZ_BG_COLORS else "black"}


def _viz_write_conf(name, params):
    """Writes cava.conf for the given params and restarts the visualizer."""
    smoothing = []
    if params.get("monstercat"):
        smoothing.append("monstercat = 1")
    if params.get("waves"):
        smoothing.append("waves = 1")
    smoothing.append(f"noise_reduction = {params['noise_reduction']}")
    norm_cava = _viz_norm_cava()
    with open(VIZ_CONF, "w", encoding="utf-8") as fh:
        fh.write(_VIZ_TEMPLATE.format(
            name=name, framerate=params["framerate"],
            bar_width=params["bar_width"], bar_spacing=params["bar_spacing"],
            color=params["color"], background=params.get("background", "black"),
            autosens=(1 if norm_cava["autosens"] else 0),
            sensitivity=norm_cava["sensitivity"],
            smoothing="\n".join(smoothing)))
    _run(["systemctl", "try-restart", VIZ_SERVICE])


def _viz_presets_list():
    """User presets from presets.json; built-in defaults (translated labels)
    until the user customizes something."""
    try:
        lst = json.load(open(VIZ_USER_PRESETS, encoding="utf-8")).get("presets", [])
        lst = [p for p in lst if p.get("id") and p.get("label")]
        if lst:
            return [{"id": str(p["id"]), "label": str(p["label"])[:24],
                     "params": _viz_clamp_params(p.get("params", {}))}
                    for p in lst]
    except Exception:  # noqa: BLE001
        pass
    return [{"id": k, "label": v["label"],
             "params": {key: v[key] for key in _VIZ_PARAM_KEYS}}
            for k, v in VIZ_PRESETS.items()]


def _viz_presets_store(lst):
    _file_write(VIZ_USER_PRESETS,
                json.dumps({"presets": lst}, ensure_ascii=False, indent=1) + "\n")


def _viz_current_preset():
    """Preset id from the cava.conf header ('custom' = hand-tuned params)."""
    try:
        first = open(VIZ_CONF, encoding="utf-8").readline()
    except OSError:
        return ""
    m = re.search(r"# preset: ([\w-]+)", first)
    if not m:
        return "custom"
    return _VIZ_LEGACY_IDS.get(m.group(1), m.group(1))


def _viz_preset_save(body):
    """Creates or updates a user preset. Returns (ok, message)."""
    if not os.path.isfile(VIZ_CONF):
        return False, T("viz_not_installed")
    label = str(body.get("label", "")).strip()[:24]
    if not label:
        return False, T("viz_name_bad")
    params = _viz_clamp_params(body)
    lst = _viz_presets_list()
    pid = str(body.get("id", ""))
    hit = next((p for p in lst if p["id"] == pid), None) if pid else None
    if hit:
        hit["label"], hit["params"] = label, params
        pid = hit["id"]
    else:
        base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "preset"
        pid, i = base, 2
        while any(p["id"] == pid for p in lst):
            pid, i = f"{base}-{i}", i + 1
        lst.append({"id": pid, "label": label, "params": params})
    _viz_presets_store(lst)
    if _viz_current_preset() == pid:
        _viz_write_conf(pid, params)   # live-update the running look
    return True, T("viz_saved").format(label=label)


def _viz_preset_delete(body):
    lst = _viz_presets_list()
    if len(lst) <= 1:
        return False, T("viz_last")
    pid = str(body.get("id", ""))
    hit = next((p for p in lst if p["id"] == pid), None)
    if not hit:
        return False, T("viz_unknown")
    lst.remove(hit)
    _viz_presets_store(lst)
    return True, T("viz_deleted").format(label=hit["label"])


def _hdmi_display_connected():
    """Whether a monitor is plugged into the HDMI port — the screen the
    visualizer draws on. Reads the KMS connector status in sysfs. Returns
    True/False, or None when it cannot be told (no DRM connector exposed, e.g.
    a legacy/fkms stack or the dev box) so the UI can stay quiet in that case."""
    files = glob.glob("/sys/class/drm/card*-HDMI-A-*/status")
    if not files:
        return None
    return any(_file_read(f).strip() == "connected" for f in files)


def _viz_state():
    installed = os.path.isfile(VIZ_CONF)
    engine, shader = _viz_engine()
    return {"installed": installed, "active": _service_active(VIZ_SERVICE),
            "enabled": _viz_enabled(),
            "hdmi_connected": _hdmi_display_connected(),
            "preset": _viz_current_preset() if installed else "",
            "params": _viz_params() if installed else None,
            "presets": [{"id": p["id"], "label": p["label"], "params": p["params"]}
                        for p in _viz_presets_list()],
            "engine": engine, "shader": shader, "scale": _viz_scale(),
            "scales": list(VIZ_SCALES), "norm": _viz_norm(),
            "glsl_error": _file_read(VIZ_GLSL_ERR).strip(),
            "glsl_available": bool(_viz_glsl_ok() and _viz_shaders()),
            "shaders": [{"id": s, "label": _shader_label(s)}
                        for s in _viz_shaders()]}


# Uploaded shaders land next to the repo ones in VIZ_GLSL_DIR — the shader
# list is a glob, so they show up (and survive updates: install.sh copies,
# never wipes). Name is a strict slug: it becomes a filename as root.
_SHADER_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_SHADER_MAX_BYTES = 64000          # viz-glsl reads the source into a 64 KiB buffer


def _viz_shader_upload(body):
    """Installs (or updates) a .frag from the panel. Returns (ok, message)."""
    if not os.path.isdir(VIZ_GLSL_DIR):
        return False, T("viz_not_installed")
    name = str(body.get("name", "")).strip().lower()
    name = re.sub(r"\.(frag|glsl|fs)$", "", name)
    if not _SHADER_NAME_RE.fullmatch(name):
        return False, T("shader_bad_name")
    src = str(body.get("source", ""))
    if len(src.encode()) > _SHADER_MAX_BYTES:
        return False, T("shader_too_big")
    if "void main" not in src or "gl_FragColor" not in src:
        return False, T("shader_bad_src")
    _file_write(os.path.join(VIZ_GLSL_DIR, name + ".frag"), src)
    engine, shader = _viz_engine()
    if engine == "glsl" and shader == name:   # updated the one on screen
        _run(["systemctl", "try-restart", VIZ_SERVICE])
    return True, T("shader_uploaded").format(name=name)


def _viz_shader_delete(body):
    name = str(body.get("id", ""))
    if not _SHADER_NAME_RE.fullmatch(name):
        return False, T("shader_bad_name")
    engine, shader = _viz_engine()
    if engine == "glsl" and shader == name:
        return False, T("shader_del_active")
    path = os.path.join(VIZ_GLSL_DIR, name + ".frag")
    if not os.path.isfile(path):
        return False, T("viz_unknown")
    os.remove(path)
    return True, T("shader_deleted").format(name=name)


def _viz_set_engine(engine, shader=""):
    """Switches cava <-> glslViewer (and picks the shader). (ok, message)."""
    if not os.path.isfile(VIZ_CONF):
        return False, T("viz_not_installed")
    if engine not in ("cava", "glsl"):
        return False, T("viz_engine_bad")
    if engine == "glsl":
        shaders = _viz_shaders()
        if not shaders or not _viz_glsl_ok():
            return False, T("viz_glsl_missing")
        if shader not in shaders:
            shader = "plasma" if "plasma" in shaders else shaders[0]
        content = f"glsl {shader}\n"
    else:
        content = "cava\n"
    _file_write(VIZ_ENGINE_FILE, content)
    _run(["systemctl", "try-restart", VIZ_SERVICE])
    return True, T("viz_engine_set").format(
        engine=_shader_label(shader) + " (glslViewer)" if engine == "glsl" else "cava")


# --- Update easter egg ------------------------------------------------------
# During a Pi software update the HDMI visualizer flips to a hidden "loading"
# shader — a white dot orbiting a white ring, its black border punching a moving
# notch into the ring (like a cut-out sliding around). The pre-update
# engine/shader is saved to a marker file and restored on the next panel startup
# (the update restarts the panel). Best-effort: only when the visualizer is
# installed, enabled and the glsl engine actually works.
VIZ_UPDATING_SHADER = "_updating"
VIZ_RESTORE_FILE = "/opt/pistream-visualizer/restore.json"
_VIZ_UPDATING_FRAG = """#ifdef GL_ES
precision mediump float;
#endif
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_level;
uniform float u_bass;
uniform float u_mid;
uniform float u_treble;

void main() {
    vec2 p = (2.0 * gl_FragCoord.xy - u_resolution) / min(u_resolution.x, u_resolution.y);
    float aa = 2.0 / min(u_resolution.x, u_resolution.y);
    float R = 0.40;
    float thick = 0.012;
    float ring = smoothstep(thick + aa, thick - aa, abs(length(p) - R));
    float a = -u_time * 1.6;                                // reversed direction
    vec2 dc = R * vec2(cos(a), sin(a));
    float d = length(p - dc);
    float beat = 1.0 + 0.55 * u_bass;                       // swells more to the beat
    float rb = 0.112 * beat;                                // bigger black rim
    float rc = 0.060 * beat;
    float border = smoothstep(rb + aa, rb - aa, d);         // black rim = cut-out
    float core = smoothstep(rc + aa, rc - aa, d);           // white dot
    vec3 col = vec3(ring);
    col *= (1.0 - border);
    col = mix(col, vec3(1.0), core);
    gl_FragColor = vec4(col, 1.0);
}
"""


def _viz_updating_on():
    """Switch the visualizer to the update spinner, saving the state to restore."""
    try:
        if (not os.path.isfile(VIZ_CONF) or os.path.isfile(VIZ_DISABLED_FLAG)
                or not _viz_glsl_ok()):
            return
        engine, shader = _viz_engine()
        _file_write(VIZ_RESTORE_FILE, json.dumps({"engine": engine, "shader": shader}))
        _file_write(os.path.join(VIZ_GLSL_DIR, VIZ_UPDATING_SHADER + ".frag"),
                    _VIZ_UPDATING_FRAG)
        _file_write(VIZ_ENGINE_FILE, f"glsl {VIZ_UPDATING_SHADER}\n")
        _run(["systemctl", "try-restart", VIZ_SERVICE])
    except Exception:  # noqa: BLE001 — an easter egg must never break an update
        pass


def _viz_restore():
    """Restore the pre-update visualizer state (once, on panel startup)."""
    try:
        if not os.path.isfile(VIZ_RESTORE_FILE):
            return
        st = json.load(open(VIZ_RESTORE_FILE, encoding="utf-8"))
        os.remove(VIZ_RESTORE_FILE)
        engine = st.get("engine", "cava")
        shader = st.get("shader", "plasma")
        _file_write(VIZ_ENGINE_FILE,
                    f"glsl {shader}\n" if engine == "glsl" else "cava\n")
        _run(["systemctl", "try-restart", VIZ_SERVICE])
        try:
            os.remove(os.path.join(VIZ_GLSL_DIR, VIZ_UPDATING_SHADER + ".frag"))
        except OSError:
            pass
    except Exception:  # noqa: BLE001
        pass


def _viz_set_preset(name):
    name = _VIZ_LEGACY_IDS.get(name, name)
    if not os.path.isfile(VIZ_CONF):
        return False, T("viz_not_installed")
    for p in _viz_presets_list():
        if p["id"] == name:
            _viz_write_conf(name, p["params"])
            return True, T("viz_preset_set").format(label=p["label"])
    return False, T("viz_unknown")


def _viz_set_params(body):
    """Custom cava parameters from the panel editor (apply without saving)."""
    if not os.path.isfile(VIZ_CONF):
        return False, T("viz_not_installed")
    _viz_write_conf("custom", _viz_clamp_params(body))
    return True, T("viz_params_set")


def _viz_enabled():
    """User intent: is the visualizer allowed to run? (No disable flag = on.)"""
    return not os.path.exists(VIZ_DISABLED_FLAG)


def _viz_toggle():
    """Flip the user's on/off intent. We persist a flag (so hdmi-watch.sh does
    not just turn it back on) and start/stop the service to match right away."""
    if _viz_enabled():
        try: _file_write(VIZ_DISABLED_FLAG, "")
        except OSError: pass
        _run(["systemctl", "stop", VIZ_SERVICE])
        return True, T("viz_stopped")
    try: os.remove(VIZ_DISABLED_FLAG)
    except OSError: pass
    _run(["systemctl", "start", VIZ_SERVICE])
    return True, T("viz_started")


# ---------------------------------------------------------------------------
# Audio output (DAC HAT vs HDMI) — the same rewrites setup.sh does in step 1
# (config.txt + snd_bcm2835 module) and step 6 (pointing the players at the
# output), so the output can be switched from the panel. The device-tree
# changes only apply after a reboot; /api/audio reports that.
# ---------------------------------------------------------------------------
BOOT_CFG = ("/boot/firmware/config.txt"
            if os.path.exists("/boot/firmware/config.txt") else "/boot/config.txt")
DAC_OVERLAY = os.environ.get("PISTREAM_DAC_OVERLAY", "allo-boss-dac-pcm512x-audio")
DAC_PCM = "hw:CARD=BossDAC,DEV=0"
RPI_AUDIO_BLACKLIST = "/etc/modprobe.d/dietpi-disable_rpi_audio.conf"
HDMI_MODULES = "/etc/modules-load.d/hdmi-audio.conf"
ASOUND_CONF = "/etc/asound.conf"
SQUEEZELITE_DEFAULT = "/etc/default/squeezelite"
SHAIRPORT_CONFS = ("/usr/local/etc/shairport-sync.conf", "/etc/shairport-sync.conf")
BLUEALSA_OVERRIDE = "/etc/systemd/system/bluealsa-aplay.service.d/override.conf"
_DAC_OVERLAY_RE = re.compile(r"^dtoverlay=(allo-boss|hifiberry)\S*", re.M)
_audio_lock = threading.Lock()


def _file_read(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def _file_write(path, txt):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(txt)
    os.replace(tmp, path)


def _cfg_set(txt, key, val):
    """config.txt: replace the key (even a commented-out one) or append it."""
    pat = re.compile(rf"^#?{re.escape(key)}=.*$", re.M)
    if pat.search(txt):
        return pat.sub(f"{key}={val}", txt)
    return txt.rstrip("\n") + f"\n{key}={val}\n"


def _audio_cfg_mode():
    """What config.txt says: 'dac' | 'hdmi' | 'unknown' (takes effect at boot)."""
    txt = _file_read(BOOT_CFG)
    if not txt:
        return "unknown"
    if _DAC_OVERLAY_RE.search(txt):
        return "dac"
    if re.search(r"^dtparam=audio=on", txt, re.M):
        return "hdmi"
    return "unknown"


def _audio_running_mode():
    """What is actually loaded right now (per /proc/asound/cards)."""
    cards = _file_read("/proc/asound/cards")
    if "BossDAC" in cards or "sndrpihifiberry" in cards:
        return "dac"
    if "bcm2835" in cards or "vc4-hdmi" in cards or "vc4hdmi" in cards:
        return "hdmi"
    return "unknown"


DAC_CARD_IDS = ("BossDAC", "sndrpihifiberry")


def _card_ids():
    """The ALSA card ids currently present, e.g. ['BossDAC', 'vc4hdmi0']."""
    ids = []
    for line in _file_read("/proc/asound/cards").splitlines():
        m = re.match(r"\s*\d+\s+\[(\S+)", line)
        if m:
            ids.append(m.group(1))
    return ids


def _dac_card_id():
    return next((c for c in _card_ids() if c in DAC_CARD_IDS), "")


def _hdmi_card_id():
    """ALSA card id of the HDMI / on-board audio, or '' if absent. Matched by
    name; falls back to the first card that is neither the DAC nor the Loopback
    (on a Pi that is the HDMI / on-board output)."""
    other = ""
    for c in _card_ids():
        if c in DAC_CARD_IDS or c == "Loopback":
            continue
        if re.search(r"hdmi|bcm2835|headphone|vc4|b1", c, re.I):
            return c
        other = other or c
    return other


def _cards_present():
    return {"dac": bool(_dac_card_id()), "hdmi": bool(_hdmi_card_id())}


# Audio-out bridge (pistream-aout.service): alsaloop copies the loopback tap to
# the real card. The panel switches output by rewriting aout.env + restarting
# that unit — no player restart, no reboot. aout.env lives in the visualizer
# dir (survives panel updates) and is the persisted output choice.
AOUT_SERVICE = "pistream-aout"
AOUT_ENV = "/opt/pistream-visualizer/aout.env"


def _card_for(mode):
    return _dac_card_id() if mode == "dac" else _hdmi_card_id()


def _aout_read():
    """(mode, card) from aout.env — the persisted output choice."""
    txt = _file_read(AOUT_ENV)

    def g(key):
        m = re.search(rf"^{key}=(\S+)", txt, re.M)
        return m.group(1) if m else ""
    return g("AOUT_MODE"), g("AOUT_CARD")


def _aout_write(mode, card):
    _file_write(AOUT_ENV, f"AOUT_MODE={mode}\nAOUT_CARD={card}\n")
    _run(["systemctl", "restart", AOUT_SERVICE])


def _audio_selected():
    """Which output is chosen (dac|hdmi), from the persisted bridge config."""
    mode, _card = _aout_read()
    if mode in ("dac", "hdmi"):
        return mode
    r = _audio_running_mode()
    return r if r != "unknown" else _audio_cfg_mode()


def _audio_state():
    cards = _cards_present()
    selected = _audio_selected()
    return {"output": selected, "running": _audio_running_mode(),
            "overlay": DAC_OVERLAY, "cards": cards,
            "hdmi_connected": _hdmi_display_connected(),
            "bridge_active": _service_active(AOUT_SERVICE),
            # the chosen output has no card up yet — needs it enabled at boot
            "reboot_required": selected in ("dac", "hdmi") and not cards.get(selected)}


def _aout_reconcile():
    """Point the bridge at the preferred card if present, else at any output
    card that IS up — runs at startup and after hardware changes so audio never
    lands on a dead/absent card (the classic silence)."""
    mode, cur = _aout_read()
    cards = _cards_present()
    if mode in ("dac", "hdmi") and cards.get(mode):
        target = mode
    elif cards["dac"]:
        target = "dac"
    elif cards["hdmi"]:
        target = "hdmi"
    else:
        return
    cid = _card_for(target)
    if cid and (target != mode or cid != cur):
        _aout_write(target, cid)


def _audio_retarget_players(pcm, card):
    """Points squeezelite / shairport-sync / bluealsa-aplay at the new output.

    Players already routed through the visualizer's 'pistream' tee are left
    alone — instead the tee's DAC slave (in the PISTREAM-VIZ asound.conf
    block) is repointed at the new card.
    """
    asound = _file_read(ASOUND_CONF)
    if "# PISTREAM-VIZ BEGIN" in asound and "# PISTREAM-VIZ END" in asound:
        pre, rest = asound.split("# PISTREAM-VIZ BEGIN", 1)
        block, post = rest.split("# PISTREAM-VIZ END", 1)
        block = re.sub(r"^(\s*card )(?!Loopback\b)\S+$", rf"\g<1>{card}",
                       block, flags=re.M)
        _file_write(ASOUND_CONF,
                    pre + "# PISTREAM-VIZ BEGIN" + block + "# PISTREAM-VIZ END" + post)

    sl = _file_read(SQUEEZELITE_DEFAULT)
    if sl and not re.search(r"-o pistream|^SL_SOUNDCARD=\"?pistream", sl, re.M):
        new = sl
        if re.search(r"^ARGS=", sl, re.M):          # DietPi: single ARGS='…' line
            if re.search(r"^ARGS=.*-o ", sl, re.M):
                new = re.sub(r"-o [^ '\"]+", f"-o {pcm}", sl)
            else:
                new = re.sub(r"^ARGS=(['\"])(.*)\1",
                             rf"ARGS=\g<1>\g<2> -o {pcm}\g<1>", sl, flags=re.M)
        elif re.search(r"^#?SL_SOUNDCARD=", sl, re.M):   # Debian package format
            new = re.sub(r"^#?SL_SOUNDCARD=.*$", f'SL_SOUNDCARD="{pcm}"',
                         sl, flags=re.M)
        elif re.search(r"-o +\S+", sl):             # legacy raw arguments
            new = re.sub(r"-o [^ '\"]+", f"-o {pcm}", sl)
        if new != sl:
            _file_write(SQUEEZELITE_DEFAULT, new)
            _run(["systemctl", "try-restart", "squeezelite"])

    for sp in SHAIRPORT_CONFS:
        txt = _file_read(sp)
        if not txt:
            continue
        if 'output_device = "pistream"' not in txt:
            new = re.sub(r'^(\s*)(//\s*)?output_device = ".*";',
                         rf'\g<1>output_device = "{pcm}";', txt, flags=re.M)
            if new != txt:
                _file_write(sp, new)
                _run(["systemctl", "try-restart", "shairport-sync"])
        break

    ovr = _file_read(BLUEALSA_OVERRIDE)
    if "pistream" not in ovr:
        os.makedirs(os.path.dirname(BLUEALSA_OVERRIDE), exist_ok=True)
        _file_write(BLUEALSA_OVERRIDE,
                    f"[Service]\nExecStart=\nExecStart=/usr/bin/bluealsa-aplay -S --pcm={pcm}\n")
        _run(["systemctl", "daemon-reload"])
        _run(["systemctl", "reset-failed", "bluealsa-aplay"])
        _run(["systemctl", "try-restart", "bluealsa-aplay"])


def _audio_set(mode):
    """Switches the audible output by pointing the audio-out bridge at that
    card and restarting it — seamless, no player restart, no reboot. Returns
    (ok, message)."""
    if mode not in ("dac", "hdmi"):
        return False, T("audio_bad")
    with _audio_lock:
        cid = _card_for(mode)
        if not cid:
            return False, T("audio_card_absent").format(out=mode.upper())
        _aout_write(mode, cid)
    return True, T("audio_set_live").format(out=mode.upper())


# ---------------------------------------------------------------------------
# Device name — one rename that follows through into the system:
#   * panel display + the persisted NAME_FILE (survives updates),
#   * Bluetooth adapter alias (what phones see while pairing),
#   * AirPlay name (shairport-sync) + LMS player name (squeezelite -n),
#   * hostname (sanitized to a valid label — drives MagicDNS and the default
#     LMS/AirPlay names for anything not overridden above).
# Every step is best-effort: off a Pi (or without a given service) it simply
# does nothing, and the panel display + NAME_FILE still take effect.
# ---------------------------------------------------------------------------
def _name_valid(name):
    name = " ".join(name.split())          # collapse/trim whitespace
    if not 1 <= len(name) <= 32:
        return None
    if any(ord(c) < 32 for c in name) or '"' in name or "\\" in name:
        return None
    return name


def _hostname_from(name):
    """A valid DNS label from a friendly name (spaces -> dashes, ASCII only)."""
    host = re.sub(r"[^A-Za-z0-9-]+", "-", name).strip("-")
    host = re.sub(r"-{2,}", "-", host)
    return host[:63] or "synchrofazotron"


def _set_hostname(host):
    _run(["hostnamectl", "set-hostname", host], timeout=10)
    hosts = _file_read("/etc/hosts")
    if hosts:
        if re.search(r"^127\.0\.1\.1\b", hosts, re.M):
            hosts = re.sub(r"^127\.0\.1\.1\b.*$", f"127.0.1.1\t{host}",
                           hosts, flags=re.M)
        else:
            hosts = hosts.rstrip("\n") + f"\n127.0.1.1\t{host}\n"
        try:
            _file_write("/etc/hosts", hosts)
        except OSError:
            pass
    # keep Tailscale's MagicDNS name in step where the CLI supports it
    _run(["tailscale", "set", "--hostname", host], timeout=10)
    return _run(["hostname"]).strip() == host


def _set_bt_alias(name):
    out = _run(["bluetoothctl", "system-alias", name], timeout=8)
    return "__err__" not in out and "Failed" not in out


def _set_airplay_name(name):
    """Sets general.name in shairport-sync.conf (edit only; caller restarts)."""
    for sp in SHAIRPORT_CONFS:
        txt = _file_read(sp)
        if not txt:
            continue
        gm = re.search(r"general\s*=\s*\{([^}]*)\}", txt, re.S)
        if not gm:
            return False
        block = gm.group(1)
        if re.search(r'(//\s*)?name\s*=\s*"[^"]*"\s*;', block):
            new_block = re.sub(r'(//\s*)?name\s*=\s*"[^"]*"\s*;',
                               f'name = "{name}";', block, count=1)
        else:
            new_block = f'\n\tname = "{name}";' + block
        new = txt[:gm.start(1)] + new_block + txt[gm.end(1):]
        if new != txt:
            _file_write(sp, new)
            return True
        return False
    return False


def _set_lms_name(name):
    """Sets the squeezelite player name via -n (edit only; caller restarts)."""
    sl = _file_read(SQUEEZELITE_DEFAULT)
    if not sl:
        return False
    if re.search(r"-n\s", sl):                          # replace existing -n
        new = re.sub(r'-n\s+("[^"]*"|\S+)', f'-n "{name}"', sl, count=1)
    elif re.search(r"^ARGS=", sl, re.M):                # DietPi single ARGS line
        new = re.sub(r"^ARGS=(['\"])(.*)\1",
                     rf'ARGS=\g<1>\g<2> -n "{name}"\g<1>', sl, flags=re.M, count=1)
    elif re.search(r'^SB_EXTRA_ARGS="', sl, re.M):      # Debian package vars
        new = re.sub(r'^SB_EXTRA_ARGS="',
                     f'SB_EXTRA_ARGS="-n \\"{name}\\" ', sl, flags=re.M, count=1)
    elif re.search(r"^#?SB_EXTRA_ARGS=", sl, re.M):
        new = re.sub(r"^#?SB_EXTRA_ARGS=.*$",
                     f'SB_EXTRA_ARGS="-n \\"{name}\\""', sl, flags=re.M, count=1)
    else:
        return False
    if new != sl:
        _file_write(SQUEEZELITE_DEFAULT, new)
        return True
    return False


def _set_device_name(name):
    """Renames the device across the system. Returns (ok, message)."""
    name = _name_valid(str(name))
    if not name:
        return False, T("name_bad")
    global DEVICE_NAME, SQUEEZELITE_PLAYER
    _file_write(NAME_FILE, name + "\n")
    DEVICE_NAME = SQUEEZELITE_PLAYER = name

    _set_hostname(_hostname_from(name))
    _set_bt_alias(name)
    # AirPlay/LMS: edit configs, then restart (the restart also lets anything
    # left on the hostname default pick up the new hostname)
    _set_airplay_name(name)
    _run(["systemctl", "try-restart", "shairport-sync"])
    _set_lms_name(name)
    _run(["systemctl", "try-restart", "squeezelite"])
    return True, T("name_set").format(name=name)


# ---------------------------------------------------------------------------
# Updates — "check" compares the installed panel file against GitHub, "run"
# re-executes setup.sh (idempotent, keeps settings) as a transient systemd
# unit. The transient unit is essential: web/install.sh restarts
# pistream-panel.service, and a child process of the panel would be killed by
# its own restart mid-update.
# ---------------------------------------------------------------------------
UPDATE_UNIT = "synchrofazotron-update"
_RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"


# Files compared against the repo by the update check — the panel code plus
# the UI files (a restyle ships without touching the .py).
_UPDATE_CHECK_FILES = ("pistream_panel.py", "ui/style.css",
                       "app/dist/index.html", "app/dist/assets/index.js")


def _update_check():
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        for rel in _UPDATE_CHECK_FILES:
            with urllib.request.urlopen(f"{_RAW_BASE}/web/{rel}", timeout=15) as r:
                remote = r.read()
            try:
                local = open(os.path.join(base, *rel.split("/")), "rb").read()
            except OSError:
                local = b""
            if remote != local:
                return {"ok": True, "update_available": True}
        return {"ok": True, "update_available": False}
    except Exception:  # noqa: BLE001
        return {"ok": False}


def _update_status():
    state = _run(["systemctl", "is-active", f"{UPDATE_UNIT}.service"])
    return {"running": state in ("active", "activating"),
            "failed": state == "failed"}


def _update_run():
    if _update_status()["running"]:
        return False, T("upd_already")
    _run(["systemctl", "reset-failed", f"{UPDATE_UNIT}.service"])
    _viz_updating_on()   # easter egg: HDMI shows the update spinner meanwhile
    _run(["systemd-run", "--unit", UPDATE_UNIT, "bash", "-c",
          f"curl -fsSL --retry 5 --retry-delay 2 {_RAW_BASE}/setup.sh | bash"],
         timeout=15)
    time.sleep(0.7)  # systemd-run reports no exit code through _run — verify
    st = _update_status()
    if not st["running"] and not st["failed"]:
        return False, T("upd_fail")
    return True, T("upd_started")


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
        rm = res.get("remoteMeta") or {}
        loop = res.get("playlist_loop") or []
        title = rm.get("title") or (loop[0].get("title", "") if loop else "")
        artist = rm.get("artist") or (loop[0].get("artist", "") if loop else "")
        return {"mode": res.get("mode", "stop"), "title": title, "artist": artist}
    except Exception:  # noqa: BLE001
        return None


# --- LMS radio browsing (TuneIn) --------------------------------------------
# TuneIn is a SlimBrowse/OPML tree. `radios` lists the top menu (Local Radio,
# Music, Podcasts, ...); `<verb> items ... menu:radio` walks each branch. Items
# are folders (browse deeper by item_id) or stations (type:audio, play by
# item_id). A station carries presetParams.favorites_url/_title/icon, which is
# exactly what `favorites add` needs — so stations can be starred.
_LMS_VERBS = {"presets", "local", "music", "sports", "news", "talk",
              "location", "language", "podcast", "search"}


def _lms_pid():
    global _lms_playerid
    if not _lms_playerid:
        loop = _lms_request(["", ["players", "0", "10"]]).get("players_loop", [])
        if loop:
            _lms_playerid = loop[0]["playerid"]
    return _lms_playerid or ""


def _lms_item_id(it):
    """item_id lives in params (stations) or in the go/play action (folders)."""
    p = it.get("params") or {}
    if p.get("item_id"):
        return str(p["item_id"])
    actions = it.get("actions") or {}
    for k in ("go", "play"):
        ap = (actions.get(k) or {}).get("params") or {}
        if ap.get("item_id"):
            return str(ap["item_id"])
    return ""


def _lms_icon(it):
    pp = it.get("presetParams") or {}
    return it.get("icon") or it.get("image") or pp.get("icon") or ""


def _lms_norm_items(result):
    items = []
    for it in result.get("item_loop", []):
        text = it.get("text") or it.get("name") or ""
        is_audio = it.get("type") == "audio" or str(it.get("isaudio")) == "1"
        pp = it.get("presetParams") or {}
        fav = None
        if pp.get("favorites_url"):
            fav = {"url": pp["favorites_url"],
                   "title": pp.get("favorites_title") or text.split("\n", 1)[0].strip(),
                   "icon": pp.get("icon") or ""}
        items.append({
            "title": text.split("\n", 1)[0].strip(),
            "icon": _lms_icon(it),
            "playable": bool(is_audio),
            "browsable": not is_audio,
            "item_id": _lms_item_id(it),
            "fav": fav,
        })
    return {"title": result.get("title", ""), "items": items}


def _lms_radio_root():
    res = _lms_request([_lms_pid(), ["radios", "0", "50"]])
    items = []
    for it in res.get("radioss_loop", []):
        verb = it.get("cmd")
        if verb not in _LMS_VERBS or verb == "search":   # search has its own box
            continue
        items.append({"title": it.get("name", ""), "icon": it.get("icon", ""),
                      "verb": verb, "browsable": True, "playable": False})
    return {"title": "Radio", "items": items}


def _lms_radio_browse(verb, item_id="", start=0, count=300):
    if verb not in _LMS_VERBS:
        return {"title": "", "items": []}
    params = [verb, "items", str(start), str(count), "menu:radio"]
    if item_id:
        params.append("item_id:" + item_id)
    out = _lms_norm_items(_lms_request([_lms_pid(), params]))
    out["verb"] = verb
    return out


def _lms_radio_search(q, start=0, count=100):
    if not q.strip():
        return {"title": "", "items": [], "verb": "search"}
    params = ["search", "items", str(start), str(count), "menu:radio", "search:" + q]
    out = _lms_norm_items(_lms_request([_lms_pid(), params]))
    out["verb"] = "search"
    return out


def _lms_radio_play(verb, item_id, add=False):
    if verb not in _LMS_VERBS or not item_id:
        return {"ok": False}
    action = "add" if add else "play"
    _lms_request([_lms_pid(), [verb, "playlist", action,
                               "menu:" + verb, "item_id:" + item_id]])
    return {"ok": True}


def _lms_favorites(item_id="", start=0, count=300):
    params = ["favorites", "items", str(start), str(count), "want_url:1"]
    if item_id:
        params.append("item_id:" + item_id)
    res = _lms_request(["", params])
    items = []
    for it in res.get("loop_loop", []):
        is_audio = str(it.get("isaudio")) == "1" or it.get("type") == "audio"
        items.append({"title": it.get("name", ""), "icon": _lms_icon(it),
                      "playable": bool(is_audio), "browsable": bool(it.get("hasitems")),
                      "id": str(it.get("id", "")), "url": it.get("url", "")})
    return {"title": res.get("title", ""), "items": items}


def _lms_fav_play(fav_id, url="", title=""):
    """Favorites stored as TuneIn directory links (Tune.ashx, sometimes with
    old partnerId/serial baggage) get resolved to the clean direct stream like
    radio-tab plays; anything else plays through the favorites plugin."""
    if url and urllib.parse.urlsplit(url).netloc in _TUNEIN_HOSTS:
        direct = _tunein_resolve(url)
        if direct:
            return _lms_play_url(direct, title)
    if not fav_id:
        return {"ok": False}
    _lms_request([_lms_pid(), ["favorites", "playlist", "play", "item_id:" + fav_id]])
    return {"ok": True}


def _lms_fav_add(url, title, icon=""):
    if not url:
        return {"ok": False}
    params = ["favorites", "add", "url:" + url, "title:" + (title or url)]
    if icon:
        params.append("icon:" + icon)
    _lms_request(["", params])
    return {"ok": True}


def _lms_fav_remove(fav_id):
    if not fav_id:
        return {"ok": False}
    _lms_request(["", ["favorites", "delete", "item_id:" + fav_id]])
    return {"ok": True}


# TuneIn-attributed sessions get preroll ads stitched in by the stream CDN
# (StreamTheWorld/Triton & co. key off dist=/aggregator= in the URL — that is
# the "Welcome to TuneIn" jingle + a geo-targeted spot). Resolving Tune.ashx
# ourselves with a bare request and dropping the attribution params keeps
# TuneIn out of the audio path; what remains is the broadcaster's own content.
_TUNEIN_HOSTS = ("opml.radiotime.com", "opml.tunein.com")
_ATTR_PARAMS = ("dist", "aggregator", "ads", "ads_partner_alias")


def _radio_deattribute(url):
    u = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
         if k.lower() not in _ATTR_PARAMS]
    return urllib.parse.urlunsplit(
        (u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), u.fragment))


def _tunein_resolve(url):
    """Tune.ashx -> the station's direct stream URL ('' when unresolvable —
    the caller then falls back to the original URL). Only the station id is
    forwarded: no partnerId/serial, nothing for TuneIn to monetize."""
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    sid = q.get("id", "")
    if not re.fullmatch(r"[st]\d+", sid):
        return ""
    try:
        with urllib.request.urlopen(
                "https://opml.radiotime.com/Tune.ashx?render=json"
                "&formats=aac,ogg,mp3&id=" + sid, timeout=6) as r:
            body = json.loads(r.read().decode("utf-8", "replace")).get("body", [])
    except Exception:  # noqa: BLE001 — TuneIn down: let LMS resolve as before
        return ""
    streams = [it for it in body if it.get("element") == "audio" and it.get("url")]
    if not streams:
        return ""
    # keep TuneIn's preference order, but direct station URLs first
    streams.sort(key=lambda it: (not it.get("is_direct"), it.get("position", 0)))
    return _radio_deattribute(streams[0]["url"])


def _lms_play_url(url, title=""):
    """Play a stream URL directly (the app browses TuneIn itself and sends
    the station's Tune.ashx URL here — resolved to a clean direct stream)."""
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"ok": False}
    if urllib.parse.urlsplit(url).netloc in _TUNEIN_HOSTS:
        url = _tunein_resolve(url) or url
    params = ["playlist", "play", url]
    if title:
        params.append(title)
    _lms_request([_lms_pid(), params])
    return {"ok": True}


# A phone opening the Radio tab fires a burst of icon requests at once; each
# used to hold its own handler thread + an LMS request (imageproxy fetches the
# image from the internet per call), which once memory-spiralled the whole Pi.
# Serve a few at a time and fail fast when saturated — the app retries lazily.
_art_sem = threading.BoundedSemaphore(4)


def _lms_art(path):
    """Fetch an LMS icon/cover so the app can load it from the panel origin
    instead of needing the LMS web port (9000) reachable from the phone — which
    also makes artwork work over Tailscale. Accepts an LMS-relative path
    (/imageproxy/…, /plugins/…, /music/…) or an absolute http(s) URL."""
    if path.startswith("/"):
        url = f"http://127.0.0.1:{LMS_PORT}{path}"
    elif path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        return None
    if not _art_sem.acquire(timeout=10):
        return None
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            return r.read(), r.headers.get("Content-Type", "image/jpeg")
    finally:
        _art_sem.release()


# ---------------------------------------------------------------------------
# TIDAL (the LMS "TIDAL local" plugin) — connect proxy
#
# The plugin runs an OAuth device flow entirely inside LMS: GETting its
# settings auth page kicks the flow off (LMS itself polls TIDAL's token
# endpoint from a Perl timer), the page carries the link.tidal.com URL and the
# deviceCode, and a tiny JSON endpoint reports when tokens have landed. The
# panel proxies those three touchpoints so the app can run the whole flow
# without ever exposing the LMS web UI. Tokens/accounts live in LMS prefs —
# the panel never sees TIDAL credentials.
# ---------------------------------------------------------------------------
TIDAL_UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "tidal-ui.json")
# LMS prefs dir differs between the legacy squeezeboxserver package and newer
# Lyrion builds — probe the known locations.
_LMS_PREFS_CANDIDATES = (
    "/var/lib/squeezeboxserver/prefs/plugin/tidal.prefs",
    "/var/lib/lyrionmusicserver/prefs/plugin/tidal.prefs",
    "/usr/share/squeezeboxserver/prefs/plugin/tidal.prefs",
)


# cached — read on every /api/status poll (the LMS source label depends on it)
_tidal_show_cache = None


def _tidal_show():
    global _tidal_show_cache
    if _tidal_show_cache is None:
        try:
            _tidal_show_cache = bool(json.load(
                open(TIDAL_UI_FILE, encoding="utf-8")).get("show", True))
        except Exception:  # noqa: BLE001 — no file yet = default on
            _tidal_show_cache = True
    return _tidal_show_cache


def _tidal_show_set(show):
    global _tidal_show_cache
    _tidal_show_cache = bool(show)
    _file_write(TIDAL_UI_FILE, json.dumps({"show": bool(show)}) + "\n")


def _lms_http(path):
    """GET an LMS web path (settings pages, plugin endpoints) as text."""
    with urllib.request.urlopen(f"http://127.0.0.1:{LMS_PORT}/{path}",
                                timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def _tidal_accounts():
    """[{'id','name'}] parsed from the plugin's prefs file (simple YAML: an
    `accounts:` hash of userId -> profile). Loose line parser on purpose — the
    panel has no YAML lib and only needs ids and display names."""
    txt = ""
    for path in _LMS_PREFS_CANDIDATES:
        txt = _file_read(path)
        if txt:
            break
    if not txt:
        return []
    accounts, cur = {}, None
    in_accounts = False
    for line in txt.splitlines():
        if not line.startswith(" "):                # top-level key
            in_accounts = line.startswith("accounts:")
            cur = None
            continue
        if not in_accounts:
            continue
        m = re.match(r"^  ['\"]?([^:'\"]+)['\"]?:\s*$", line)
        if m:                                        # userId key
            cur = m.group(1)
            accounts[cur] = {}
            continue
        m = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if m and cur:
            accounts[cur][m.group(1)] = m.group(2).strip("'\"")
    return [{"id": uid,
             "name": (a.get("nickname") or a.get("firstName")
                      or a.get("fullName") or a.get("username") or uid)}
            for uid, a in accounts.items()]


def _tidal_plugin_state():
    """'enabled'/'disabled'/... or '' when the plugin (or LMS) is missing."""
    try:
        res = _lms_request(["", ["pref", "plugin.state:TIDAL", "?"]])
        return str(res.get("_p2", ""))
    except Exception:  # noqa: BLE001 — LMS down
        return ""


def _tidal_status():
    state = _tidal_plugin_state()
    return {"available": state == "enabled", "plugin_state": state,
            "show": _tidal_show(), "accounts": _tidal_accounts()}


def _tidal_auth_start():
    """Kick off the device flow and hand the app the link + code. Each call
    starts a fresh flow (the previous code simply expires in LMS)."""
    try:
        html = _lms_http("plugins/TIDAL/settings/auth.html")
    except OSError:
        return {"ok": False}
    link = re.search(r"https?://link\.tidal\.com/[A-Za-z0-9]+", html)
    code = re.search(r'name="deviceCode"[^>]*value="([^"]+)"', html)
    if not (link and code):
        return {"ok": False}
    return {"ok": True, "link": link.group(0), "code": code.group(1)}


def _tidal_auth_status(code):
    """The plugin drops the code from its cache once tokens arrive — but also
    when the code expires, so 'done' alone is not success: the app checks that
    an account actually appeared (returned here to save a round trip)."""
    done = False
    if code:
        try:
            j = json.loads(_lms_http(
                "plugins/TIDAL/settings/hasCredentials?deviceCode="
                + urllib.parse.quote(code)))
            done = bool(j.get("hasCredentials"))
        except (OSError, ValueError):
            pass
    return {"done": done, "accounts": _tidal_accounts()}


def _tidal_forget(account_id):
    """Remove one account via the plugin settings handler (delete_<id> param
    runs unconditionally there)."""
    if not re.fullmatch(r"[\w.-]+", account_id or ""):
        return {"ok": False}
    try:
        _lms_http("plugins/TIDAL/settings.html?delete_"
                  + urllib.parse.quote(account_id) + "=1")
        return {"ok": True, "accounts": _tidal_accounts()}
    except OSError:
        return {"ok": False}


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


# Who holds the audio output right now. A stream that is open but silent
# (e.g. a paused squeezelite before its -C 5 timeout closes the device) still
# blocks the single-substream DAC — that is the classic reason Bluetooth or
# AirPlay produce no sound, so the panel shows it explicitly.
_UNIT_LABELS = {
    "squeezelite.service": "LMS (squeezelite)",
    "shairport-sync.service": "AirPlay (shairport-sync)",
    "bluealsa-aplay.service": "Bluetooth (bluealsa-aplay)",
    "raspotify.service": "Spotify (raspotify)",
}


def _dac_owners():
    """[{'unit','label','running'}] for every unit holding a playback stream."""
    holding = _alsa_playback_units(running_only=False)
    running = _alsa_playback_units(running_only=True)
    return [{"unit": u, "label": _UNIT_LABELS.get(u, u), "running": u in running}
            for u in sorted(holding)]


def _active_sources(connected):
    """Returns the list of sources with their playback state."""
    sources = []
    lms = _lms_state()
    if lms is not None:
        state = {"play": T("state_playing"),
                 "pause": T("state_paused")}.get(lms["mode"], T("state_idle"))
        # the "hide TIDAL" toggle only changes how the source is presented —
        # LMS itself (and a connected account) is untouched
        name = "LMS (radio/TIDAL)" if _tidal_show() else "LMS (radio)"
        sources.append({"name": name, "playing": lms["mode"] == "play",
                        "state": state, "detail": lms.get("title", ""),
                        "artist": lms.get("artist", "")})

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
        s.setdefault("id", {"LMS (radio/TIDAL)": "lms", "LMS (radio)": "lms",
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
    """action: 'play' | 'pause' | 'toggle' | 'next' | 'prev'.
    Returns True when a command was sent."""
    if source == "lms":
        if not (_lms_playerid or _lms_state()):
            return False
        if action in ("next", "prev"):
            cmd = ["playlist", "index", "+1" if action == "next" else "-1"]
        else:
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
        meth = {"pause": "Pause", "next": "Next", "prev": "Previous"}.get(action, "Play")
        return "__err__" not in _run(
            ["busctl", "call", "org.bluez", p, "org.bluez.MediaPlayer1", meth])

    if source == "airplay":
        meth = {"pause": "Pause", "play": "Play",
                "next": "Next", "prev": "Previous"}.get(action, "PlayPause")
        return "__err__" not in _run(
            ["busctl", "call", "org.mpris.MediaPlayer2.ShairportSync",
             "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", meth])

    return False


# ---------------------------------------------------------------------------
# Per-source volume. Each player owns its own (software) volume — the same knob
# the controlling app moves — so we drive each through its native API and
# normalise to 0-100:
#   LMS      -> jsonrpc `mixer volume`             (already 0-100)
#   AirPlay  -> shairport MPRIS `Volume` property  (0.0-1.0)
#   Bluetooth-> bluealsa-cli on the A2DP PCM        (0-127, AVRCP absolute)
# get returns None when the source isn't present/controllable right now.
# ---------------------------------------------------------------------------
def _bt_a2dp_path():
    """D-Bus path of the A2DP sink stream (phone -> Pi), or None."""
    for path in _run(["bluealsa-cli", "list-pcms"]).splitlines():
        path = path.strip()
        if "a2dp" in path:
            return path
    return None


def _vol_lms_get():
    pid = _lms_pid()
    if not pid:
        return None
    v = _lms_request([pid, ["mixer", "volume", "?"]]).get("_volume")
    return None if v is None else max(0, min(100, int(round(float(v)))))


def _vol_lms_set(value):
    pid = _lms_pid()
    if not pid:
        return False
    _lms_request([pid, ["mixer", "volume", str(value)]])
    return True


# AirPlay volume is a dB value in [-30, 0] (a large negative == muted). The MPRIS
# Volume is read-only, so use shairport's own writable org.gnome.ShairportSync
# Volume property and map it to/from 0-100.
_AP_SVC = "org.gnome.ShairportSync"
_AP_OBJ = "/org/gnome/ShairportSync"
_AP_DB_LO = -30.0


def _vol_airplay_get():
    out = _run(["busctl", "get-property", _AP_SVC, _AP_OBJ, _AP_SVC, "Volume"])
    m = re.search(r"-?\d+(?:\.\d+)?", out)
    if not m:
        return None
    db = float(m.group(0))
    if db <= _AP_DB_LO:
        return 0
    if db >= 0:
        return 100
    return max(0, min(100, int(round((db - _AP_DB_LO) / -_AP_DB_LO * 100))))


def _vol_airplay_set(value):
    db = _AP_DB_LO + (value / 100.0) * (-_AP_DB_LO)   # 0 -> -30dB, 100 -> 0dB
    # `--` so busctl doesn't parse the negative dB value as an option flag
    return "__err__" not in _run(
        ["busctl", "set-property", _AP_SVC, _AP_OBJ, _AP_SVC, "Volume", "d", "--", f"{db:.2f}"])


def _vol_bt_get():
    p = _bt_a2dp_path()
    if not p:
        return None
    nums = re.findall(r"\d+", _run(["bluealsa-cli", "volume", p]))
    return None if not nums else max(0, min(100, int(round(int(nums[0]) / 127 * 100))))


def _vol_bt_set(value):
    p = _bt_a2dp_path()
    if not p:
        return False
    raw = max(0, min(127, int(round(value / 100 * 127))))
    return "__err__" not in _run(["bluealsa-cli", "volume", p, str(raw)])


_VOL_GET = {"lms": _vol_lms_get, "airplay": _vol_airplay_get, "bt": _vol_bt_get}
_VOL_SET = {"lms": _vol_lms_set, "airplay": _vol_airplay_set, "bt": _vol_bt_set}


def _volume_payload():
    """Current volume (0-100) per available source; absent = not controllable now."""
    out = {}
    for sid, fn in _VOL_GET.items():
        try:
            v = fn()
        except Exception:  # noqa: BLE001
            v = None
        if v is not None:
            out[sid] = v
    return {"volumes": out}


def _volume_set(source, value=None, delta=None):
    """Set absolute value or apply a delta. Returns (ok, new_value|None)."""
    if source not in _VOL_SET:
        return False, None
    if delta is not None:
        cur = None
        try:
            cur = _VOL_GET[source]()
        except Exception:  # noqa: BLE001
            cur = None
        if cur is None:
            return False, None
        value = cur + delta
    if value is None:
        return False, None
    value = max(0, min(100, int(value)))
    try:
        ok = _VOL_SET[source](value)
    except Exception:  # noqa: BLE001
        ok = False
    return ok, (value if ok else None)


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
        "wifi_ssid": _wifi_ssid(),
        "connected": [{"mac": m, "name": n} for m, n in connected],
        "lms_playerid": _lms_playerid or "",
        "sources": sources,
        "dac_owners": _dac_owners(),
        "playing_count": sum(1 for s in sources if s.get("playing")),
        "services": {
            s: _service_active(s) for s in (
                ("bluetooth", "bluealsa", "bluealsa-aplay", "squeezelite",
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
    html = html.replace("{{LMS_PORT}}", str(LMS_PORT))
    html = html.replace("{{REPO}}", REPO)
    return html


UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")


def _i18n_payload(host_header):
    """Everything the Preact bundle needs at boot in one request: the active
    language, all translated strings (with {{DEVICE}} etc. already substituted),
    and the handful of config values the UI references. STR stays the single
    source of truth — the bundle carries no baked-in copy, so it stays static
    and drops unchanged into a WebView / native shell later."""
    base = dict(STR["en"])
    base.update(STR.get(_lang, {}))      # same en-fallback semantics as T()
    strings = {k: _fill(v, host_header) for k, v in base.items()}
    return {
        "lang": _lang,
        "langs": list(LANGS),
        "device": DEVICE_NAME,
        "player": SQUEEZELITE_PLAYER,
        "lms_port": LMS_PORT,
        "pair_win": PAIR_WINDOW_SEC,
        "repo": REPO,
        "version": VERSION,
        "strings": strings,
    }


# The shader studio is a self-contained HTML app from visualizer/ — served
# when present (on the Pi: copied by visualizer/install.sh; in a repo
# checkout: straight from the source tree).
STUDIO_CANDIDATES = (
    "/opt/pistream-visualizer/visualizer-studio.html",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "visualizer", "visualizer-studio.html"),
)


def _studio_html():
    for p in STUDIO_CANDIDATES:
        txt = _file_read(p)
        if txt:
            return txt
    return ""


def static_file(path):
    """(body, content_type) for /static/<name> — now just the shared stylesheet
    the SPA links (ui/style.css). basename() kills any path traversal attempt."""
    name = os.path.basename(path.split("?", 1)[0])
    full = os.path.join(UI_DIR, name)
    if os.path.isfile(full) and name.endswith(".css"):
        return _file_read(full), "text/css; charset=utf-8"
    return None


# The Preact panel (web/app/) is built on the laptop into app/dist and served
# here as a flat static mount under /app/. Hash routing means there are no
# server-side SPA routes to special-case: /app and /app/ serve index.html,
# everything else maps straight to a file in dist. No Node ever runs on the Pi.
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "dist")

_APP_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}


def app_file(path):
    """(body_bytes, content_type) for a path under /app/, or None if unbuilt or
    unknown. Traversal-safe: the resolved path must stay inside APP_DIR."""
    rel = path[len("/app"):].split("?", 1)[0].lstrip("/")
    if not rel:
        rel = "index.html"
    full = os.path.normpath(os.path.join(APP_DIR, rel))
    if os.path.commonpath([full, APP_DIR]) != APP_DIR or not os.path.isfile(full):
        return None
    ext = os.path.splitext(full)[1].lower()
    try:
        with open(full, "rb") as fh:
            return fh.read(), _APP_MIME.get(ext, "application/octet-stream")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SynchrofazotronPanel/1.0"

    def _send(self, code, body, ctype="text/html; charset=utf-8", no_cache=False):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # The Android/WebView shell loads the bundle from the app itself
        # (capacitor://localhost) and calls the panel cross-origin, so every
        # response is CORS-open. No auth yet (panel lives behind Tailscale/LAN);
        # tightening this is tracked with the pairing work.
        self.send_header("Access-Control-Allow-Origin", "*")
        if no_cache:
            # /app ships with stable (unhashed) filenames, so make the browser
            # revalidate — otherwise a panel update would serve stale JS.
            self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_app(self, app_path):
        hit = app_file(app_path)
        if hit:
            self._send(200, hit[0], hit[1], no_cache=True)
        else:
            self._send(404, "panel app not built (run: cd web/app && npm run build)",
                       "text/plain")

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001
            return {}

    def do_OPTIONS(self):
        # CORS preflight for the app's JSON POSTs (Content-Type triggers it).
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        # The Preact SPA is the whole UI: "/" serves its index.html and /app/*
        # serves the bundle (index.html links assets by absolute /app/assets path,
        # so it runs fine from the root). Hash routing → no server SPA routes.
        if self.path == "/" or self.path.startswith("/?"):
            self._serve_app("/app")
        elif self.path == "/app" or self.path.startswith("/app/"):
            self._serve_app(self.path)
        elif self.path == "/settings" or self.path.startswith("/settings?"):
            self._redirect("/#/settings")      # legacy full-page URL → SPA route
        elif self.path.startswith("/static/"):
            hit = static_file(self.path)
            if hit:
                self._send(200, hit[0], hit[1])
            else:
                self._send(404, "not found", "text/plain")
        elif self.path == "/studio":
            studio = _studio_html()
            if studio:
                self._send(200, studio)
            else:
                self._send(404, "studio not installed", "text/plain")
        elif self.path == "/api/tailscale":
            self._send(200, json.dumps(_tailscale_state()), "application/json")
        elif self.path == "/api/sources":
            self._send(200, json.dumps(_sources_payload()), "application/json")
        elif self.path == "/api/status":
            self._send(200, json.dumps(status_payload()), "application/json")
        elif self.path == "/api/volume":
            self._send(200, json.dumps(_volume_payload()), "application/json")
        elif self.path == "/api/wifi":
            self._send(200, json.dumps(_wifi_payload()), "application/json")
        elif self.path == "/api/wifi/scan":
            self._send(200, json.dumps({"networks": _wifi_scan_networks()}),
                       "application/json")
        elif self.path == "/api/viz":
            self._send(200, json.dumps(_viz_state()), "application/json")
        elif self.path == "/api/audio":
            self._send(200, json.dumps(_audio_state()), "application/json")
        elif self.path == "/api/bt":
            self._send(200, json.dumps(_bt_payload()), "application/json")
        elif self.path == "/api/bt/debug":
            self._send(200, json.dumps(_bt_debug()), "application/json")
        elif self.path == "/api/update":
            self._send(200, json.dumps(_update_status()), "application/json")
        elif self.path == "/api/update/check":
            self._send(200, json.dumps(_update_check()), "application/json")
        elif self.path == "/api/lang":
            self._send(200, json.dumps({"lang": _lang, "available": LANGS}),
                       "application/json")
        elif self.path == "/api/i18n":
            self._send(200, json.dumps(_i18n_payload(self.headers.get("Host", ""))),
                       "application/json")
        elif self.path.startswith("/api/lms/art?"):
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                art = _lms_art((q.get("path") or [""])[0])
            except Exception:  # noqa: BLE001 — LMS down / bad path
                art = None
            if art:
                self._send(200, art[0], art[1])
            else:
                self._send(404, "no art", "text/plain")
        elif self.path == "/api/tidal":
            self._send(200, json.dumps(_tidal_status()), "application/json",
                       no_cache=True)
        elif self.path.startswith("/api/tidal/auth/status"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = (q.get("code") or [""])[0]
            self._send(200, json.dumps(_tidal_auth_status(code)),
                       "application/json", no_cache=True)
        elif self.path.startswith("/api/lms/"):
            self._send(200, json.dumps(self._lms_get()), "application/json",
                       no_cache=True)
        elif self.path == "/healthz":
            self._send(200, "ok", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def _lms_get(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        def g(key, default=""):
            return (q.get(key) or [default])[0]

        try:
            if u.path == "/api/lms/radio":
                return _lms_radio_root()
            if u.path == "/api/lms/radio/browse":
                return _lms_radio_browse(g("verb"), g("item_id"))
            if u.path == "/api/lms/radio/search":
                return _lms_radio_search(g("q"))
            if u.path == "/api/lms/favorites":
                return _lms_favorites(g("item_id"))
        except Exception:  # noqa: BLE001 — LMS down / unexpected shape
            return {"items": [], "error": "lms"}
        return {"items": [], "error": "unknown"}

    def do_POST(self):
        if self.path == "/api/pair":
            _start_pairing()
            self._send(200, json.dumps({"ok": True, "seconds": _pair_seconds_left()}),
                       "application/json")
        elif self.path == "/api/audio/test":
            ok, message = _audio_test()
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/bt/connect":
            ok, message = _bt_connect(str(self._json_body().get("mac", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/bt/disconnect":
            ok, message = _bt_disconnect(str(self._json_body().get("mac", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/bt/forget":
            ok, message = _bt_forget(str(self._json_body().get("mac", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/bt/reconnect":
            body = self._json_body()
            cfg = _bt_reconnect_set(body.get("enabled"), body.get("interval", 45))
            self._send(200, json.dumps({"ok": True, **cfg}), "application/json")
        elif self.path == "/api/tailscale/set":
            ok, message = _tailscale_set(bool(self._json_body().get("up")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/source/toggle":
            body = self._json_body()
            ok, message = _source_toggle(str(body.get("source", "")),
                                         bool(body.get("enable")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/tidal/auth/start":
            self._send(200, json.dumps(_tidal_auth_start()), "application/json")
        elif self.path == "/api/tidal/show":
            show = bool(self._json_body().get("show"))
            _tidal_show_set(show)
            self._send(200, json.dumps({"ok": True, "show": show}),
                       "application/json")
        elif self.path == "/api/tidal/forget":
            self._send(200, json.dumps(
                _tidal_forget(str(self._json_body().get("id", "")))),
                "application/json")
        elif self.path == "/api/name":
            ok, message = _set_device_name(self._json_body().get("name", ""))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/control":
            body = self._json_body()
            ok = _control(str(body.get("source", "")), str(body.get("action", "toggle")))
            self._send(200, json.dumps({"ok": ok}), "application/json")
        elif self.path == "/api/volume":
            body = self._json_body()
            v, d = body.get("value"), body.get("delta")
            ok, newv = _volume_set(
                str(body.get("source", "")),
                value=(int(v) if v is not None else None),
                delta=(int(d) if d is not None else None))
            self._send(200, json.dumps({"ok": ok, "value": newv}), "application/json")
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
        elif self.path == "/api/viz/preset/save":
            ok, message = _viz_preset_save(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/preset/delete":
            ok, message = _viz_preset_delete(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/normalize":
            ok, message = _viz_set_normalize(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/shader/upload":
            ok, message = _viz_shader_upload(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/shader/delete":
            ok, message = _viz_shader_delete(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/params":
            ok, message = _viz_set_params(self._json_body())
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/engine":
            body = self._json_body()
            ok, message = _viz_set_engine(str(body.get("engine", "")),
                                          str(body.get("shader", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/toggle":
            ok, message = _viz_toggle()
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/viz/scale":
            ok, message = _viz_set_scale(str(self._json_body().get("scale", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/audio/set":
            body = self._json_body()
            ok, message = _audio_set(str(body.get("output", "")))
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/update/run":
            ok, message = _update_run()
            self._send(200, json.dumps({"ok": ok, "message": message}),
                       "application/json")
        elif self.path == "/api/reboot":
            self._send(200, json.dumps({"ok": True}), "application/json")
            threading.Timer(1.0, lambda: _run(["systemctl", "reboot"])).start()
        elif self.path == "/api/lang":
            body = self._json_body()
            ok = _lang_set(str(body.get("lang", "")))
            self._send(200, json.dumps({"ok": ok, "lang": _lang,
                                        "message": T("lang_set") if ok else ""}),
                       "application/json")
        elif self.path.startswith("/api/lms/"):
            self._send(200, json.dumps(self._lms_post(self.path, self._json_body())),
                       "application/json")
        else:
            self._send(404, "not found", "text/plain")

    def _lms_post(self, path, b):
        try:
            if path == "/api/lms/radio/play":
                return _lms_radio_play(str(b.get("verb", "")), str(b.get("item_id", "")),
                                       bool(b.get("add")))
            if path == "/api/lms/playurl":
                return _lms_play_url(str(b.get("url", "")), str(b.get("title", "")))
            if path == "/api/lms/favorites/play":
                return _lms_fav_play(str(b.get("id", "")), str(b.get("url", "")),
                                     str(b.get("title", "")))
            if path == "/api/lms/favorites/add":
                return _lms_fav_add(str(b.get("url", "")), str(b.get("title", "")),
                                    str(b.get("icon", "")))
            if path == "/api/lms/favorites/remove":
                return _lms_fav_remove(str(b.get("id", "")))
        except Exception:  # noqa: BLE001 — LMS down / unexpected shape
            return {"ok": False, "error": "lms"}
        return {"ok": False, "error": "unknown"}

    # Quiet by default; set PISTREAM_DEBUG_HTTP=1 on the service (systemctl
    # edit) to log every request — handy when chasing what a phone app
    # actually fetches (or doesn't).
    debug_http = bool(os.environ.get("PISTREAM_DEBUG_HTTP"))

    def log_message(self, fmt, *args):
        if self.debug_http:
            print(self.address_string() + " " + (fmt % args), flush=True)


def main():
    if not DEV_MODE:   # the background loops only poke real system services
        _viz_restore()      # restore visualizer if we came back from an update
        _aout_reconcile()   # point the audio-out bridge at a present card
        threading.Thread(target=_auto_trust_loop, daemon=True).start()
        if BT_AUTOCONNECT:
            threading.Thread(target=_bt_autoconnect_loop, daemon=True).start()
        if AUTOPAUSE:
            threading.Thread(target=_autopause_loop, daemon=True).start()
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    # 0.0.0.0 means "every interface" — print an address a browser can open
    host = "127.0.0.1" if BIND in ("0.0.0.0", "::") else BIND
    print(f"Synchrofazotron panel at http://{host}:{PORT}")
    if DEV_MODE:
        print("  sandbox mode: system commands are disabled (no hostname / "
              "tailscale / systemctl / bluetooth changes).")
        print("  set PISTREAM_DEV=0 to run for real on the device.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
