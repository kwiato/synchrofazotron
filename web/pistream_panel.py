#!/usr/bin/env python3
"""
PiStream control panel — lekki mikroserwis (tylko stdlib).

Serwuje mobilną stronę HTML z:
  * przyciskiem "Włącz parowanie Bluetooth" (ustawia discoverable/pairable
    na określony czas i trzyma agenta BT, żeby telefon sparował się bez
    potwierdzania po stronie Pi),
  * instrukcjami co i jak można odtwarzać na tym urządzeniu.

Bez zależności zewnętrznych — działa na czystym DietPi / Raspberry Pi OS.
Domyślnie nasłuchuje na 0.0.0.0:8787 (dostępny przez Tailscale i LAN).
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
# Konfiguracja (dostosuj pod siebie; wszystko można nadpisać przez env)
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PISTREAM_PANEL_PORT", "8787"))
BIND = os.environ.get("PISTREAM_PANEL_BIND", "0.0.0.0")

_HOSTNAME = socket.gethostname() or "PiStream"
DEVICE_NAME = os.environ.get("PISTREAM_NAME", _HOSTNAME)   # nazwa BT / AirPlay
LMS_PORT = 9000                    # port webowego UI Lyrion Music Server
SQUEEZELITE_PLAYER = os.environ.get("PISTREAM_LMS_PLAYER", _HOSTNAME)
PAIR_WINDOW_SEC = 180             # jak długo Pi jest widoczne przy parowaniu
SHOW_SPOTIFY = os.environ.get("PISTREAM_SPOTIFY", "0") == "1"  # raspotify niezainstalowany
WIFI_IFACE = os.environ.get("PISTREAM_WIFI_IFACE", "wlan0")

# ---------------------------------------------------------------------------
# Sterowanie Bluetooth
# ---------------------------------------------------------------------------
_pair_lock = threading.Lock()
_pair_deadline = 0.0               # unix ts, do kiedy trwa okno parowania
_trusted = set()                   # cache: MAC-i którym już ustawiono trust


def _run(cmd, timeout=8):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"__err__ {e}"


def _bt_show():
    return _run(["bluetoothctl", "show"])


def _connected_devices():
    """Zwraca listę [(mac, name)] połączonych urządzeń BT."""
    out = _run(["bluetoothctl", "devices", "Connected"])
    devices = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 3 and parts[0] == "Device":
            devices.append((parts[1], parts[2]))
    return devices


def _start_pairing(window=PAIR_WINDOW_SEC):
    """Włącza widoczność/parowalność na czas okna.

    Auto-akceptacją parowania (Just Works) zajmuje się osobna, trwała usługa
    `bt-agent -c NoInputNoOutput` — dlatego tu NIE rejestrujemy własnego agenta
    (dwa agenty by kolidowały). Headless Pi niczego nie musi potwierdzać.
    """
    global _pair_deadline
    with _pair_lock:
        was_active = _pair_deadline > time.time()
        _pair_deadline = time.time() + window
        _run(["bluetoothctl", "power", "on"])
        _run(["bluetoothctl", "pairable", "on"])
        _run(["bluetoothctl", "discoverable", "on"])
        if was_active:
            return  # wątek zamykający już działa, tylko przedłużyliśmy okno

        def _closer():
            while time.time() < _pair_deadline:
                time.sleep(1)
            _run(["bluetoothctl", "discoverable", "off"])
            _run(["bluetoothctl", "pairable", "off"])

        threading.Thread(target=_closer, daemon=True).start()


def _auto_trust_loop():
    """W tle: nadaje 'trust' połączonym urządzeniom, żeby wracały same."""
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
# Wi-Fi — zarządzanie przez bazę sieci DietPi (do 5 slotów).
#
# DietPi trzyma znane sieci w /var/lib/dietpi/dietpi-wifi.db (format bash:
# aWIFI_SSID[n]='...', aWIFI_KEY[n]='...', aWIFI_KEYMGR[n]='WPA-PSK'),
# a `dietpi-wifidb 1` generuje z niej wpa_supplicant.conf. Piszemy do bazy
# zamiast wprost do wpa_supplicant, żeby dietpi-config widział te same sieci.
# ---------------------------------------------------------------------------
WIFI_DB = "/var/lib/dietpi/dietpi-wifi.db"
WIFI_APPLY_CMD = ["/boot/dietpi/func/dietpi-wifidb", "1"]
WIFI_SLOTS = 5
_WIFI_LINE = re.compile(r"^aWIFI_(\w+)\[(\d+)\]='(.*)'$")
_wifi_lock = threading.Lock()


def _wifi_db_read():
    """Zwraca {slot: {pole: wartość}} z bazy sieci DietPi."""
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
        # pola WPA-EAP itp. zachowujemy, jeśli slot je miał
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
    """Regeneruje wpa_supplicant.conf z bazy i każe wpa_supplicant przeładować.

    Reconfigure nie zrywa aktywnego połączenia, jeśli bieżąca sieć dalej jest
    na liście — dlatego /api/wifi/remove nie pozwala usunąć bieżącej sieci.
    """
    out = _run(WIFI_APPLY_CMD, timeout=30)
    rec = _run(["wpa_cli", "-i", WIFI_IFACE, "reconfigure"], timeout=10)
    return {"apply": out, "reconfigure": rec,
            "reloaded": rec.strip().endswith("OK")}


def _wifi_current():
    """Bieżące połączenie: {'ssid','signal','ip'} lub None."""
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
    """Skanuje otoczenie: [{'ssid','signal'}] posortowane po sile sygnału."""
    out = _run(["iw", "dev", WIFI_IFACE, "scan"], timeout=25)
    if "__err__" in out or "busy" in out.lower():
        time.sleep(2)  # radio bywa chwilowo zajęte (wspólne z BT)
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


def _wifi_payload():
    slots = _wifi_db_read()
    saved = [{"slot": i, "ssid": s.get("SSID", ""), "keymgr": s.get("KEYMGR", "")}
             for i, s in sorted(slots.items()) if s.get("SSID")]
    return {"iface": WIFI_IFACE, "current": _wifi_current(), "saved": saved,
            "free_slots": WIFI_SLOTS - len(saved)}


def _wifi_add(ssid, key):
    """Dodaje/aktualizuje sieć. Zwraca (ok, komunikat)."""
    ssid, key = ssid.strip(), key.strip()
    if not ssid or len(ssid.encode()) > 32:
        return False, "Nieprawidłowy SSID."
    if key and not 8 <= len(key) <= 63:
        return False, "Hasło WPA musi mieć 8–63 znaki (puste = sieć otwarta)."
    with _wifi_lock:
        slots = _wifi_db_read()
        target = None
        for i, s in slots.items():
            if s.get("SSID") == ssid:
                target = i  # aktualizacja istniejącej
                break
        if target is None:
            for i in range(WIFI_SLOTS):
                if not slots.get(i, {}).get("SSID"):
                    target = i
                    break
        if target is None:
            return False, f"Brak miejsca — DietPi mieści {WIFI_SLOTS} sieci. Usuń jakąś."
        slots[target] = {"SSID": ssid, "KEY": key,
                         "KEYMGR": "WPA-PSK" if key else "NONE"}
        _wifi_db_write(slots)
        res = _wifi_apply()
    msg = f"Zapisano „{ssid}” (slot {target})."
    if not res["reloaded"]:
        msg += " Uwaga: przeładowanie wpa_supplicant nie potwierdziło się — sieć zadziała najpóźniej po restarcie."
    return True, msg


def _wifi_remove(slot):
    with _wifi_lock:
        slots = _wifi_db_read()
        s = slots.get(slot)
        if not s or not s.get("SSID"):
            return False, "Pusty slot."
        cur = _wifi_current()
        if cur and cur["ssid"] == s["SSID"]:
            return False, "To sieć, przez którą jesteś teraz połączony — nie usunę jej zdalnie."
        ssid = s["SSID"]
        slots[slot] = {}
        _wifi_db_write(slots)
        _wifi_apply()
    return True, f"Usunięto „{ssid}”."


# ---------------------------------------------------------------------------
# Wykrywanie "kto teraz gra"
#
# Uwaga architektoniczna: nie ma centralnego menedżera audio (jak PulseAudio /
# PipeWire), więc źródła NIE pauzują się nawzajem. Na wyjściu HDMI (bcm2835,
# 8 subkanałów) grają równolegle i się MIKSUJĄ. Na sprzętowym DAC-u (1 subkanał)
# pierwszy zajmuje wyjście, kolejne dostają "device busy". Ten wskaźnik pokazuje
# co jest aktywne, żeby wiadomo było co zatrzymać.
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
    """Zwraca {'mode','title'} playera Squeezelite lub None."""
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
    """Lista strumieni A2DP: [{'mac','running'}] (Running=true => realnie gra)."""
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


def _alsa_active_units():
    """Zbiór systemd unitów trzymających RUNNING strumień wyjściowy ALSA."""
    active = set()
    for f in glob.glob("/proc/asound/card*/pcm*p/sub*/status"):
        try:
            txt = open(f).read()
        except Exception:  # noqa: BLE001
            continue
        if "state: RUNNING" not in txt:
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


def _active_sources(connected):
    """Zwraca listę źródeł z ich stanem odtwarzania."""
    sources = []
    lms = _lms_state()
    if lms is not None:
        state = {"play": "gra", "pause": "pauza"}.get(lms["mode"], "cisza")
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
                        "state": "gra" if bt_playing else "połączony",
                        "detail": bt_detail or ", ".join(conn.values())})

    units = _alsa_active_units()
    unit_map = [("shairport-sync.service", "AirPlay", "airplay", True)]
    if SHOW_SPOTIFY:
        unit_map.append(("raspotify.service", "Spotify", "spotify", False))
    for unit, label, sid, ctl in unit_map:
        if unit in units:
            sources.append({"name": label, "id": sid, "playing": True,
                            "state": "gra", "detail": "", "controllable": ctl})

    # id + controllable dla LMS/BT (dodane wyżej bez tych pól)
    for s in sources:
        s.setdefault("controllable", True)
        s.setdefault("id", {"LMS (radio/TIDAL)": "lms",
                            "Bluetooth": "bt"}.get(s["name"], ""))
    return sources


# ---------------------------------------------------------------------------
# Sterowanie odtwarzaniem (play/pause) per źródło
# ---------------------------------------------------------------------------
def _bt_player_path():
    m = re.search(r"/org/bluez/hci0/dev_[0-9A-Fa-f_]+/player\d+",
                  _run(["busctl", "tree", "org.bluez"]))
    return m.group(0) if m else None


def _control(source, action):
    """action: 'play' | 'pause' | 'toggle'. Zwraca True gdy wysłano komendę."""
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
# Strona HTML
# ---------------------------------------------------------------------------
def _fill(template, host_header):
    lms_host = host_header.split(":")[0] if host_header else DEVICE_NAME
    lms_url = f"http://{lms_host}:{LMS_PORT}/material"
    html = template
    if not SHOW_SPOTIFY:
        html = re.sub(r"<!--SPOTIFY-->.*?<!--/SPOTIFY-->", "", html, flags=re.S)
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
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{DEVICE}} — panel</title>
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
    <a href="/settings" style="text-decoration:none; font-size:1.3rem;" title="Ustawienia">⚙️</a>
  </div>
  <p class="sub">Panel sterowania odtwarzaczem audio</p>

  <div class="card">
    <h2>🎚️ Teraz gra</h2>
    <div id="warn" class="note" style="display:none; margin:0 0 10px;">
      ⚠️ Kilka źródeł gra jednocześnie — pierwsze zajmuje DAC, reszta gra w próżnię.
      Zatrzymaj niepotrzebne.
    </div>
    <div id="sources"><p class="muted">…</p></div>
    <p class="muted" style="margin-top:8px;">Źródła nie pauzują się nawzajem —
       każde trzeba zatrzymać w swojej apce.</p>
  </div>

  <div class="card">
    <h2>📶 Bluetooth</h2>
    <p>Kliknij, żeby urządzenie stało się widoczne i gotowe do sparowania
       przez <b>{{PAIR_WIN}} sekund</b>. Potem w telefonie: Bluetooth →
       wybierz <b>{{DEVICE}}</b>.</p>
    <button id="pairBtn" class="btn" onclick="pair()">🔵 Włącz parowanie Bluetooth</button>
    <div class="status-line">
      <span>Status BT:</span>
      <span id="btState" class="pill off">…</span>
      <span id="btConn" class="muted"></span>
    </div>
    <p class="muted step">Po sparowaniu możesz grać z <b>dowolnej apki</b> na telefonie
       (YouTube Music, podcasty, cokolwiek) — dźwięk poleci na {{DEVICE}}.</p>
  </div>

  <!--SPOTIFY-->
  <div class="card">
    <h2>🟢 Spotify</h2>
    <p><span class="num">1</span>Otwórz apkę <b>Spotify</b> na telefonie/PC.</p>
    <p><span class="num">2</span>Dotknij ikony urządzeń (Spotify Connect) i wybierz
       <b>{{DEVICE}}</b>.</p>
    <p class="muted">Nie trzeba nic parować — działa po sieci.</p>
  </div>
  <!--/SPOTIFY-->

  <div class="card">
    <h2>🍎 AirPlay</h2>
    <p><span class="num">1</span>Na iPhone/iPad/Mac otwórz Centrum sterowania lub
       ikonę AirPlay w apce muzycznej.</p>
    <p><span class="num">2</span>Wybierz <b>{{DEVICE}}</b> jako głośnik.</p>
  </div>

  <div class="card">
    <h2>🎧 TIDAL / radio / biblioteka (Lyrion Music Server)</h2>
    <p><span class="num">1</span>Zainstaluj apkę <b>Squeezer</b> (Android) lub
       <b>iPeng</b> (iOS) — to główny pilot.</p>
    <p><span class="num">2</span>Wybierz odtwarzacz <b>{{PLAYER}}</b> i graj
       TIDAL, radio internetowe, playlisty.</p>
    <p>Albo z przeglądarki: <a href="{{LMS_URL}}">{{LMS_URL}}</a> (Material Skin).</p>
  </div>

  <div class="card note">
    <h2>ℹ️ Uwaga o dźwięku</h2>
    <p class="muted">Dźwięk wychodzi przez <b>DAC</b> (BossDAC). Grające źródło zajmuje
       DAC na wyłączność i zwalnia go kilka sekund po zatrzymaniu — jeśli coś "nie chce
       zagrać", sprawdź wyżej, co jeszcze gra.</p>
  </div>

  <p class="muted" style="text-align:center; margin-top:24px;">
    Odtwarzacze: <span id="svc"></span>
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
      btState.textContent = 'parowanie: ' + left + 's';
      btState.className = 'pill on';
      setBtn(true, left);
    } else {
      btState.textContent = s.bt_powered ? 'gotowy' : 'wyłączony';
      btState.className = 'pill ' + (s.bt_powered ? 'on' : 'off');
      setBtn(false, 0);
    }
    const conn = s.connected || [];
    document.getElementById('btConn').textContent =
      conn.length ? ('połączone: ' + conn.map(d=>d.name).join(', ')) : '';

    // "Teraz gra"
    const src = s.sources || [];
    const box = document.getElementById('sources');
    if (!src.length) {
      box.innerHTML = '<p class="muted">Cisza — nic nie gra.</p>';
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
          btn = '<button class="tbtn" disabled title="steruj z apki źródła">▶</button>';
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
    b.textContent = '✅ Parowanie aktywne — szukaj "{{DEVICE}}" (' + left + 's)';
  } else {
    b.classList.remove('active');
    b.textContent = '🔵 Włącz parowanie Bluetooth';
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
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{DEVICE}} — ustawienia</title>
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
</style>
</head>
<body>
<div class="wrap">
  <div style="display:flex; align-items:baseline; justify-content:space-between;">
    <h1>⚙️ Ustawienia</h1>
    <a href="/" style="text-decoration:none;">← panel</a>
  </div>
  <p class="sub">{{DEVICE}}</p>

  <div class="card">
    <h2>📡 Wi-Fi — bieżące połączenie</h2>
    <p id="wifiNow" class="muted">…</p>
  </div>

  <div class="card">
    <h2>💾 Zapisane sieci</h2>
    <p class="muted">Pi łączy się automatycznie z pierwszą dostępną z tej listy
       (DietPi mieści maks. 5). Idealne na sieć domową + drugą lokalizację.</p>
    <div id="saved"><p class="muted">…</p></div>
  </div>

  <div class="card">
    <h2>➕ Dodaj sieć</h2>
    <p class="muted">Wpisz ręcznie (sieci spoza zasięgu też można — SSID co do znaku!)
       albo wybierz ze skanu.</p>
    <input id="ssid" placeholder="Nazwa sieci (SSID)" autocomplete="off">
    <input id="key" type="password" placeholder="Hasło (puste = sieć otwarta)"
           autocomplete="new-password">
    <button class="btn" id="addBtn" onclick="addNet()">Zapisz sieć</button>
    <button class="btn sec" id="scanBtn" onclick="scan()">🔍 Skanuj otoczenie</button>
    <div id="scanOut"></div>
    <p id="msg" class="muted"></p>
  </div>

  <div class="card">
    <h2>ℹ️ Jak to działa</h2>
    <p class="muted">Sieci trafiają do bazy DietPi (tej samej, którą widzi
       <code>dietpi-config</code>), a konfiguracja Wi-Fi jest przeładowywana w locie —
       bez restartu. Usunięcie sieci, przez którą aktualnie jesteś połączony,
       jest zablokowane, żeby nie odciąć sobie dostępu.</p>
  </div>
</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/api/wifi', {cache:'no-store'});
    const w = await r.json();
    const cur = w.current;
    document.getElementById('wifiNow').innerHTML = cur
      ? '<span class="pill on">połączony</span> <b>' + escapeHtml(cur.ssid) + '</b>'
        + (cur.ip ? ' — ' + cur.ip : '')
        + (cur.signal != null ? ' <span class="muted">(' + cur.signal + ' dBm)</span>' : '')
      : '<span class="pill off">brak połączenia</span>';
    const box = document.getElementById('saved');
    const saved = w.saved || [];
    box.innerHTML = saved.length ? saved.map(s =>
      '<div class="row"><div class="info">' +
      (cur && cur.ssid === s.ssid ? '🟢 ' : '') + '<b>' + escapeHtml(s.ssid) + '</b>' +
      ' <span class="muted">slot ' + s.slot + '</span></div>' +
      '<button class="xbtn" title="usuń" onclick="removeNet(' + s.slot + ',\\'' +
      escapeHtml(s.ssid).replace(/'/g, "\\\\'") + '\\')">🗑</button></div>'
    ).join('') : '<p class="muted">Brak zapisanych sieci.</p>';
  } catch(e) {}
}

async function addNet() {
  const ssid = document.getElementById('ssid').value;
  const key = document.getElementById('key').value;
  const b = document.getElementById('addBtn');
  b.disabled = true; msg('Zapisuję…');
  try {
    const r = await fetch('/api/wifi/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ssid, key})
    });
    const j = await r.json();
    msg(j.message || (j.ok ? 'OK' : 'Błąd'));
    if (j.ok) { document.getElementById('ssid').value='';
                document.getElementById('key').value=''; }
  } catch(e) { msg('Błąd połączenia.'); }
  b.disabled = false;
  refresh();
}

async function removeNet(slot, ssid) {
  if (!confirm('Usunąć sieć „' + ssid + '”?')) return;
  try {
    const r = await fetch('/api/wifi/remove', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({slot})
    });
    const j = await r.json();
    msg(j.message || '');
  } catch(e) { msg('Błąd połączenia.'); }
  refresh();
}

async function scan() {
  const b = document.getElementById('scanBtn');
  b.disabled = true; b.textContent = '🔍 Skanuję… (kilka sekund)';
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
      : '<p class="muted">Nic nie znaleziono (radio bywa zajęte — spróbuj ponownie).</p>';
  } catch(e) { msg('Skan nie wyszedł — spróbuj ponownie.'); }
  b.disabled = false; b.textContent = '🔍 Skanuj otoczenie';
}

function pick(ssid) {
  document.getElementById('ssid').value = ssid;
  document.getElementById('key').focus();
}

function msg(t) { document.getElementById('msg').textContent = t; }

function escapeHtml(s) {
  return (s||'').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "PiStreamPanel/1.0"

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
            self._send(200, json.dumps({"networks": _wifi_scan()}), "application/json")
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
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args):  # cisza w logach
        pass


def main():
    threading.Thread(target=_auto_trust_loop, daemon=True).start()
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"PiStream panel na http://{BIND}:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
