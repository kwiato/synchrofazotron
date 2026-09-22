"""PC plugin — Wake-on-LAN for a computer on the same LAN.

Lifted from pimote (github.com/kwiato/pimote), minus the USB keyboard: waking
needs no cable, only a magic packet on the LAN broadcast, so it fits any
Synchrofazotron. The keyboard half (HID gadget) is a separate plugin.

State: plugins-data/pc/config.json = {"mac": "AA:BB:...", "host": "192.168..."}.
API (under /api/p/pc):
  GET  /state   -> {mac, host, online: true|false|null, last_wake: unix ts|0}
  POST /wake    -> {ok, message}
  POST /config  {mac, host} -> {ok, message, mac, host}
"""
import json
import os
import re
import socket
import subprocess
import time

_ctx = None
_cfg_path = ""
_last_wake = 0.0
_MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]{0,253}$")


def setup(ctx):
    global _ctx, _cfg_path
    _ctx = ctx
    _cfg_path = os.path.join(ctx["data_dir"], "config.json")


def _config():
    try:
        with open(_cfg_path, encoding="utf-8") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        c = {}
    return {"mac": str(c.get("mac", "")), "host": str(c.get("host", ""))}


def _save(cfg):
    os.makedirs(os.path.dirname(_cfg_path), exist_ok=True)
    with open(_cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)


def _norm_mac(raw):
    """'aa-bb-cc-dd-ee-ff' / 'aabb.ccdd.eeff' -> 'AA:BB:CC:DD:EE:FF' or ''."""
    hexd = re.sub(r"[^0-9A-Fa-f]", "", raw or "")
    if len(hexd) != 12:
        return ""
    return ":".join(hexd[i:i + 2] for i in range(0, 12, 2)).upper()


def _magic(mac):
    """6 x FF + the MAC 16 times, sent as UDP broadcast on the usual ports."""
    payload = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(payload, ("255.255.255.255", port))


def _online(host):
    """True/False from one ping, None when there is nothing to check (no host
    set, sandbox). ping -c1 -W1 exists on DietPi out of the box."""
    if not host or _ctx["dev"]:
        return None
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "1", host],
                           capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:  # noqa: BLE001 — no ping binary / timeout
        return None


def handle(method, path, body, query):
    global _last_wake
    cfg = _config()
    if method == "GET" and path == "/state":
        return {**cfg, "online": _online(cfg["host"]), "last_wake": _last_wake}
    if method == "POST" and path == "/wake":
        if not cfg["mac"]:
            return {"ok": False, "message": "no_mac"}
        if _ctx["dev"]:
            return {"ok": False, "message": "sandbox"}
        _magic(cfg["mac"])
        _last_wake = time.time()
        _ctx["log"](f"wake {cfg['mac']}")
        return {"ok": True, "message": "sent", "last_wake": _last_wake}
    if method == "POST" and path == "/config":
        mac_raw = str(body.get("mac", "")).strip()
        mac = _norm_mac(mac_raw)
        if mac_raw and not _MAC_RE.match(mac):
            return {"ok": False, "message": "bad_mac"}
        host = str(body.get("host", "")).strip()
        if not _HOST_RE.match(host):
            return {"ok": False, "message": "bad_host"}
        cfg = {"mac": mac, "host": host}
        _save(cfg)
        return {"ok": True, "message": "saved", **cfg}
    return None
