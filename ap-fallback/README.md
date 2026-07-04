# Synchrofazotron setup-AP fallback ("Chromecast mode")

When the device cannot join any known Wi-Fi for ~2 minutes — new location,
changed router password, first boot without `dietpi-wifi.txt` — it raises its
own access point with a captive portal, so any phone can hand it the local
Wi-Fi credentials. No app, no SSH, no monitor needed.

## User flow

1. The device sits with no Wi-Fi for ~2 min → the network
   **`Synchrofazotron-Setup`** appears (password: **`synchrofazotron`**).
2. Connect a phone to it. The phone's "sign in to network" captive portal
   opens the control panel (if it does not, go to `http://192.168.4.1`).
3. Open ⚙️ `/settings` → add the local network — pick it from the scan
   (a snapshot taken just before the AP went up) or type it in manually.
4. On save the AP tears itself down and the device joins the new network.
   If that fails (typo in the password), the AP comes back after ~2 minutes.

## How it works

```
pistream-net-watch.service  ->  net-watch.sh (permanent loop, every 10 s)
  no "Connected to" on wlan0 for 2 min:
    1. curl the panel /api/wifi/scan  -> /run/pistream-ap-scan.json (cache)
    2. ifdown wlan0, static 192.168.4.1, hostapd + dnsmasq (our configs)
    3. dnsmasq answers every DNS query with 192.168.4.1 and iptables
       redirects :80 to the panel port -> captive portal
    4. marker /run/pistream-ap.active tells the panel to serve the cached
       scan (the shared radio cannot scan while being an AP)
  the DietPi Wi-Fi db changes (panel saved a network) OR 10 min pass:
    5. AP down, ifup wlan0, retry normal Wi-Fi for 2 min; repeat if needed
```

Timings and addresses are constants at the top of `net-watch.sh`. The AP
window (10 min) guarantees a transient router outage cannot leave the device
stuck in setup mode: it keeps retrying normal Wi-Fi between AP windows.

## Install / update

Installed by `setup.sh` by default (`PISTREAM_AP_FALLBACK=0` to skip), or
standalone:

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/ap-fallback/install.sh | sudo bash
```

An edited `hostapd.conf` (custom SSID/password) survives updates — the new
default lands next to it as `hostapd.conf.new`. Undo everything:

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/ap-fallback/uninstall.sh | sudo bash
```

## Testing on a live device

```bash
# simulate "no Wi-Fi" (the AP should come up ~2 min later):
sudo ifdown wlan0
# watch what net-watch is doing:
journalctl -fu pistream-net-watch
# after testing, either configure via the AP or just:
sudo systemctl restart pistream-net-watch   # cleanup + back to normal
```

## Notes & limitations

- The Zero 2 W has a **single radio** shared by Wi-Fi and BT: while the AP is
  up there is no internet on the device and no live scanning (hence the
  snapshot). Music sources that need the network are down in setup mode anyway.
- The portal accepts real Wi-Fi passwords over plain HTTP on the setup AP —
  that is why the AP is WPA2-protected rather than open.
- If the phone shows "connected, no internet" and no portal, open
  `http://192.168.4.1` by hand (some Androids suppress the portal for
  WPA2 networks).
- `ifup`/`ifdown` (ifupdown + wpa_supplicant) is assumed — that is how DietPi
  manages `wlan0`. Not NetworkManager-compatible as is.

## Files

| File | Goes to | Role |
|---|---|---|
| `net-watch.sh` | `/opt/pistream-ap/` | watchdog + AP state machine |
| `hostapd.conf` | `/opt/pistream-ap/` | the setup AP (SSID/password) |
| `dnsmasq.conf` | `/opt/pistream-ap/` | DHCP + catch-all DNS for the portal |
| `pistream-net-watch.service` | `/etc/systemd/system/` | runs the watchdog (enabled) |
