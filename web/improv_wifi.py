#!/usr/bin/env python3
"""
Synchrofazotron — Improv Wi-Fi BLE provisioning service.

A standalone BlueZ D-Bus GATT server implementing the Improv Wi-Fi BLE
standard (https://www.improv-wifi.com/ble/). It lets a companion app hand
Wi-Fi credentials to a brand-new / relocated device over Bluetooth LE
*before* the device is on any network — solving the chicken-and-egg that
otherwise needs the setup-AP captive portal.

Why a separate service (not part of the panel): the control panel is
stdlib-only, but a GATT server needs D-Bus (python3-dbus + python3-gi).
So this runs as its own systemd unit (pistream-improv.service). To avoid
duplicating the DietPi Wi-Fi-DB logic it does NOT write wpa_supplicant
itself — it POSTs the credentials to the panel's own /api/wifi/add on
localhost (the panel listens on 127.0.0.1:8787 even with no network), which
already validates, writes the DietPi DB and reloads wpa_supplicant.

Improv contract implemented here (byte-exact):
  Service   00467768-6228-2272-4663-277478268000
  chars     ...2680 01 Current State  (read, notify)
            ...2680 02 Error State    (read, notify)
            ...2680 03 RPC Command    (write)
            ...2680 04 RPC Result     (read, notify)
            ...2680 05 Capabilities   (read)
  RPC pkt   [cmd][len][data...][checksum = sum(prev) & 0xFF]
            cmd 0x01 Wi-Fi = ssid_len|ssid|pass_len|pass ; cmd 0x02 Identify

No external dependencies beyond python3-dbus + python3-gi (both from apt).
"""

import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
import urllib.error

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PANEL_URL = os.environ.get("PISTREAM_PANEL_LOCAL", "http://127.0.0.1:8787")
PANEL_PORT = int(os.environ.get("PISTREAM_PANEL_PORT", "8787"))
HOSTNAME = socket.gethostname() or "synchrofazotron"
CONNECT_TIMEOUT_SEC = int(os.environ.get("PISTREAM_IMPROV_TIMEOUT", "35"))
# Re-check "am I on Wi-Fi?" this often; advertise only while offline.
ONLINE_POLL_SEC = 15

# ---------------------------------------------------------------------------
# Improv Wi-Fi constants (https://www.improv-wifi.com/ble/)
# ---------------------------------------------------------------------------
IMPROV_SVC_UUID = "00467768-6228-2272-4663-277478268000"
UUID_CURRENT_STATE = "00467768-6228-2272-4663-277478268001"
UUID_ERROR_STATE = "00467768-6228-2272-4663-277478268002"
UUID_RPC_COMMAND = "00467768-6228-2272-4663-277478268003"
UUID_RPC_RESULT = "00467768-6228-2272-4663-277478268004"
UUID_CAPABILITIES = "00467768-6228-2272-4663-277478268005"

# Current State
STATE_AUTH_REQUIRED = 0x01
STATE_AUTHORIZED = 0x02
STATE_PROVISIONING = 0x03
STATE_PROVISIONED = 0x04

# Error State
ERR_NONE = 0x00
ERR_INVALID_RPC = 0x01
ERR_UNKNOWN_CMD = 0x02
ERR_UNABLE_TO_CONNECT = 0x03
ERR_NOT_AUTHORIZED = 0x04
ERR_UNKNOWN = 0xFF

# RPC commands
CMD_SEND_WIFI = 0x01
CMD_IDENTIFY = 0x02

# Capabilities bitfield: bit0 = supports Identify
CAPABILITY_IDENTIFY = 0x01

BLUEZ = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADV_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADV_IFACE = "org.bluez.LEAdvertisement1"


def log(msg):
    print(f"[improv] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Improv packet helpers
# ---------------------------------------------------------------------------
def _checksum(data):
    return sum(data) & 0xFF


def build_rpc_result(command, strings):
    """Improv RPC result frame: [cmd][len][ (slen|sbytes)... ][checksum]."""
    payload = bytearray()
    for s in strings:
        b = s.encode("utf-8")
        payload.append(len(b) & 0xFF)
        payload.extend(b)
    frame = bytearray([command & 0xFF, len(payload) & 0xFF])
    frame.extend(payload)
    frame.append(_checksum(frame))
    return bytes(frame)


def parse_rpc_command(buf):
    """Validate + parse an Improv RPC command frame.

    Returns (command, data_bytes) on success, or raises ValueError with an
    Improv error code attached as .improv_err.
    """
    if len(buf) < 3:
        e = ValueError("short frame")
        e.improv_err = ERR_INVALID_RPC
        raise e
    command = buf[0]
    length = buf[1]
    # frame = cmd + len + <length data bytes> + checksum
    if len(buf) < 2 + length + 1:
        e = ValueError("truncated frame")
        e.improv_err = ERR_INVALID_RPC
        raise e
    body = buf[: 2 + length]
    checksum = buf[2 + length]
    if _checksum(body) != checksum:
        e = ValueError("bad checksum")
        e.improv_err = ERR_INVALID_RPC
        raise e
    return command, bytes(buf[2 : 2 + length])


def decode_wifi_payload(data):
    """cmd 0x01 data = ssid_len | ssid | pass_len | pass -> (ssid, password)."""
    if len(data) < 1:
        raise ValueError("no ssid length")
    slen = data[0]
    if len(data) < 1 + slen + 1:
        raise ValueError("ssid overruns frame")
    ssid = data[1 : 1 + slen].decode("utf-8", "replace")
    plen = data[1 + slen]
    off = 2 + slen
    if len(data) < off + plen:
        raise ValueError("password overruns frame")
    password = data[off : off + plen].decode("utf-8", "replace")
    return ssid, password


# ---------------------------------------------------------------------------
# Wi-Fi provisioning via the panel (reuses its DietPi-DB write + reload)
# ---------------------------------------------------------------------------
def panel_wifi_add(ssid, key):
    """POST the creds to the local panel. Returns (ok, message)."""
    body = json.dumps({"ssid": ssid, "key": key}).encode("utf-8")
    req = urllib.request.Request(
        f"{PANEL_URL}/api/wifi/add", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode("utf-8", "replace"))
        return bool(res.get("ok")), str(res.get("message", ""))
    except Exception as e:  # noqa: BLE001
        return False, f"panel unreachable: {e}"


def panel_wifi_current():
    """Current SSID per the panel, or '' if none/unknown."""
    try:
        with urllib.request.urlopen(f"{PANEL_URL}/api/wifi", timeout=5) as r:
            cur = (json.loads(r.read().decode("utf-8", "replace"))
                   or {}).get("current")
        return (cur or {}).get("ssid", "") if cur else ""
    except Exception:  # noqa: BLE001
        return ""


def wait_for_connection(ssid, timeout=CONNECT_TIMEOUT_SEC):
    """Blocks until the panel reports we are on `ssid` (with an IP), or times out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if panel_wifi_current() == ssid:
            return True
        time.sleep(2)
    return False


# ---------------------------------------------------------------------------
# BlueZ GATT server scaffolding (dbus-python + GLib), following the canonical
# bluez test/example-gatt-server + example-advertisement structure.
# ---------------------------------------------------------------------------
class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class FailedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.Failed"


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/pl/synchrofazotron/improv"
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for chrc in service.characteristics:
                response[chrc.get_path()] = chrc.get_properties()
        return response


class Service(dbus.service.Object):
    PATH_BASE = "/pl/synchrofazotron/improv/service"

    def __init__(self, bus, index, uuid, primary):
        self.path = f"{self.PATH_BASE}{index}"
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {GATT_SERVICE_IFACE: {
            "UUID": self.uuid,
            "Primary": self.primary,
            "Characteristics": dbus.Array(
                [c.get_path() for c in self.characteristics], signature="o"),
        }}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, chrc):
        self.characteristics.append(chrc)


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = f"{service.path}/char{index}"
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.notifying = False
        self.value = []  # list of dbus.Byte
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {GATT_CHRC_IFACE: {
            "Service": self.service.get_path(),
            "UUID": self.uuid,
            "Flags": self.flags,
        }}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def set_value(self, data):
        """Update the value and, if a client subscribed, notify it."""
        self.value = [dbus.Byte(b) for b in data]
        if self.notifying:
            self.PropertiesChanged(
                GATT_CHRC_IFACE, {"Value": dbus.Array(self.value, signature="y")}, [])

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        props = dict(self.get_properties()[GATT_CHRC_IFACE])
        props["Value"] = dbus.Array(self.value, signature="y")
        return props

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return self.value

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        self.notifying = False


# ---------------------------------------------------------------------------
# Improv characteristics
# ---------------------------------------------------------------------------
class CurrentStateChrc(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_CURRENT_STATE, ["read", "notify"], service)
        self.value = [dbus.Byte(STATE_AUTHORIZED)]


class ErrorStateChrc(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_ERROR_STATE, ["read", "notify"], service)
        self.value = [dbus.Byte(ERR_NONE)]


class RpcResultChrc(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_RPC_RESULT, ["read", "notify"], service)
        self.value = [dbus.Byte(0)]


class CapabilitiesChrc(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_CAPABILITIES, ["read"], service)
        self.value = [dbus.Byte(CAPABILITY_IDENTIFY)]


class RpcCommandChrc(Characteristic):
    """The one writable characteristic — receives Improv RPC commands."""

    def __init__(self, bus, index, service, improv):
        super().__init__(bus, index, UUID_RPC_COMMAND,
                         ["write", "write-without-response"], service)
        self.improv = improv
        self._buf = bytearray()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        self._buf.extend(bytes(bytearray(value)))
        # Try to parse a complete frame; keep buffering if truncated.
        try:
            command, data = parse_rpc_command(self._buf)
        except ValueError as e:
            need = None
            if len(self._buf) >= 2:
                need = 2 + self._buf[1] + 1
            if need and len(self._buf) < need:
                return  # partial write — wait for the rest
            self._buf.clear()
            self.improv.set_error(getattr(e, "improv_err", ERR_INVALID_RPC))
            return
        self._buf.clear()
        self.improv.handle_command(command, data)


# ---------------------------------------------------------------------------
# LE advertisement — legacy HCI, NOT BlueZ's LEAdvertisement1.
#
# BlueZ drives *extended* advertising on this controller (it reports BT 5.0),
# and the Pi's CYW43438 firmware rejects "LE Set Extended Advertising Data"
# with Invalid Parameters (0x0d) — even for an empty PDU (confirmed with
# btmon). Its *legacy* (BT 4.0) advertising HCI commands work fine, so we
# program advertising directly: connectable ADV_IND carrying Flags + the
# 128-bit Improv service UUID. BlueZ still owns the GATT server (registered
# via GattManager1) and serves it over the incoming LE connection.
# ---------------------------------------------------------------------------
HCI_DEV = os.environ.get("PISTREAM_IMPROV_HCI", "hci0")


def _le_uuid_bytes(uuid):
    """128-bit UUID as advertised (little-endian) bytes."""
    return bytes.fromhex(uuid.replace("-", ""))[::-1]


def _hci_cmd(ogf, ocf, *data_bytes):
    args = ["hcitool", "-i", HCI_DEV, "cmd", ogf, ocf] + list(data_bytes)
    try:
        subprocess.run(args, capture_output=True, timeout=6)
    except Exception as e:  # noqa: BLE001
        log(f"hci cmd {ocf} failed: {e}")


def hci_adv_enable():
    """Program + enable legacy connectable advertising with the Improv UUID."""
    # AD: Flags(LE General Disc + BR/EDR not supported) + complete 128-bit UUID
    ad = bytes([0x02, 0x01, 0x06, 0x11, 0x07]) + _le_uuid_bytes(IMPROV_SVC_UUID)
    siglen = len(ad)
    data = " ".join(f"{b:02x}" for b in ad.ljust(31, b"\x00")).split()
    # LE Set Advertising Parameters: ADV_IND, ~100 ms, all channels
    _hci_cmd("0x08", "0x0006", "A0", "00", "A0", "00", "00", "00", "00",
             "00", "00", "00", "00", "00", "00", "07", "00")
    # LE Set Advertising Data: significant length + 31 data bytes
    _hci_cmd("0x08", "0x0008", f"{siglen:02x}", *data)
    # LE Set Advertising Enable
    _hci_cmd("0x08", "0x000A", "01")


def hci_adv_disable():
    _hci_cmd("0x08", "0x000A", "00")


# ---------------------------------------------------------------------------
# Improv state machine — glue between the characteristics and Wi-Fi
# ---------------------------------------------------------------------------
class Improv:
    def __init__(self):
        self.state = None
        self.error = None
        self.result = None
        self._provisioning = False

    def bind(self, state_chrc, error_chrc, result_chrc):
        self.state = state_chrc
        self.error = error_chrc
        self.result = result_chrc

    def set_state(self, s):
        log(f"state -> 0x{s:02x}")
        self.state.set_value([s])

    def set_error(self, e):
        if e != ERR_NONE:
            log(f"error -> 0x{e:02x}")
        self.error.set_value([e])

    def handle_command(self, command, data):
        self.set_error(ERR_NONE)
        if command == CMD_IDENTIFY:
            log("identify")
            return
        if command == CMD_SEND_WIFI:
            if self._provisioning:
                return
            try:
                ssid, password = decode_wifi_payload(data)
            except ValueError as e:
                log(f"bad wifi payload: {e}")
                self.set_error(ERR_INVALID_RPC)
                return
            self._provisioning = True
            self.set_state(STATE_PROVISIONING)
            # Do the (blocking) join off the D-Bus thread.
            GLib.idle_add(self._do_provision, ssid, password)
            return
        log(f"unknown command 0x{command:02x}")
        self.set_error(ERR_UNKNOWN_CMD)

    def _do_provision(self, ssid, password):
        log(f"provisioning ssid={ssid!r}")
        ok, message = panel_wifi_add(ssid, password)
        if not ok:
            log(f"panel wifi_add failed: {message}")
            self.set_error(ERR_UNABLE_TO_CONNECT)
            self.set_state(STATE_AUTHORIZED)
            self._provisioning = False
            return False
        if wait_for_connection(ssid):
            url = f"http://{HOSTNAME}:{PANEL_PORT}"
            log(f"connected; redirect={url}")
            self.result.set_value(build_rpc_result(CMD_SEND_WIFI, [url]))
            self.set_state(STATE_PROVISIONED)
        else:
            log("saved but did not confirm a connection in time")
            self.set_error(ERR_UNABLE_TO_CONNECT)
            self.set_state(STATE_AUTHORIZED)
        self._provisioning = False
        return False  # one-shot idle callback


# ---------------------------------------------------------------------------
# Adapter discovery + registration
# ---------------------------------------------------------------------------
def find_adapter(bus):
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), DBUS_OM_IFACE)
    for path, ifaces in om.GetManagedObjects().items():
        if GATT_MANAGER_IFACE in ifaces:
            return path
    return None


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        log("no BlueZ adapter with GattManager1 — is bluetooth up?")
        raise SystemExit(1)
    log(f"adapter: {adapter}")

    # Power the adapter on.
    props = dbus.Interface(bus.get_object(BLUEZ, adapter), DBUS_PROP_IFACE)
    try:
        props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    except dbus.exceptions.DBusException as e:
        log(f"could not power on adapter: {e}")

    improv = Improv()

    app = Application(bus)
    service = Service(bus, 0, IMPROV_SVC_UUID, True)
    state_chrc = CurrentStateChrc(bus, 0, service)
    error_chrc = ErrorStateChrc(bus, 1, service)
    rpc_cmd = RpcCommandChrc(bus, 2, service, improv)
    result_chrc = RpcResultChrc(bus, 3, service)
    caps_chrc = CapabilitiesChrc(bus, 4, service)
    for chrc in (state_chrc, error_chrc, rpc_cmd, result_chrc, caps_chrc):
        service.add_characteristic(chrc)
    app.add_service(service)
    improv.bind(state_chrc, error_chrc, result_chrc)

    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter), GATT_MANAGER_IFACE)

    mainloop = GLib.MainLoop()

    def register_app_reply():
        log("GATT application registered")

    def register_app_error(error):
        log(f"failed to register GATT application: {error}")
        mainloop.quit()

    adv_state = {"on": False}
    force_adv = os.environ.get("PISTREAM_IMPROV_FORCE_ADV") == "1"

    def do_enable_adv():
        hci_adv_enable()  # idempotent — re-asserting is harmless
        if not adv_state["on"]:
            adv_state["on"] = True
            log("advertising Improv (legacy HCI, device is offline)")

    def do_disable_adv():
        hci_adv_disable()
        if adv_state["on"]:
            adv_state["on"] = False
            log("stopped advertising (device is online)")

    def online_gate():
        """Advertise Improv only while the device is NOT on Wi-Fi.

        A legacy connectable advertisement stops when a central connects, so
        we re-assert it here periodically (skipping the window where a
        provisioning session is mid-flight). PISTREAM_IMPROV_FORCE_ADV=1 keeps
        advertising on regardless (for testing on a box that is online)."""
        if improv._provisioning:
            return True
        on_wifi = bool(panel_wifi_current())
        if on_wifi and not force_adv:
            do_disable_adv()
        else:
            do_enable_adv()
        return True  # keep polling

    gatt_mgr.RegisterApplication(
        app.get_path(), {},
        reply_handler=register_app_reply,
        error_handler=register_app_error)

    def _shutdown(*_):
        do_disable_adv()
        mainloop.quit()
        return False

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, _shutdown)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, _shutdown)

    # First gate check shortly after startup, then periodically.
    GLib.timeout_add_seconds(1, lambda: (online_gate(), False)[1])
    GLib.timeout_add_seconds(ONLINE_POLL_SEC, online_gate)

    log("Improv Wi-Fi service running")
    mainloop.run()


if __name__ == "__main__":
    main()
