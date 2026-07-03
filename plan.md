# PiStream — plan konfiguracji

## Sprzęt
- Raspberry Pi Zero 2 W (512 MB RAM)
- InnoMaker DAC Mini HAT (PCM5122)
- Hammer-header (press-fit)

## Status sprzętu (DO ROZWIĄZANIA)
- DAC nie jest wykrywany: `i2cdetect -y 1` pusty (brak `4d`), czerwony LED zgasł.
- Zasilanie Pi OK (`vcgencmd get_throttled` = 0x0), więc kabel/zasilacz nie jest winny.
- Najprawdopodobniej problem z kontaktem hammer-headera (nie dociśnięty równo / słaby styk).
- Następne kroki: multimetr (sprawdzić 3.3V/5V na pinach headera) lub ponowne/porządne
  dociśnięcie headera; ewentualnie test DAC na innym Pi.
- UWAGA: nie montować pod kątem — ryzyko zwarcia sąsiednich pinów.

## OS
- DietPi Lite 64-bit (Bookworm), headless
- Konfiguracja bezgłowa przed 1. bootem: `dietpi-wifi.txt` (SSID+hasło),
  `dietpi.txt` → `AUTO_SETUP_SSH_SERVER_INDEX=-2`

## Sterownik DAC (overlay)
- Wg instrukcji InnoMaker: `dtoverlay=allo-boss-dac-pcm512x-audio`
  (NIE hifiberry — to była zła próba; karta pokaże się jako "BossDAC")
- Ustawić w: `dietpi-config → Audio Options → Sound card → allo-boss-dac-pcm512x-audio`
- Weryfikacja: `aplay -l` (karta BossDAC), `alsamixer` (kontrolka Digital), `speaker-test`

## RAM / stabilność
- zram: `apt install zram-tools`, w `/etc/default/zramswap` → `ALGO=zstd`, `PERCENT=50`
- Swap zostawić domyślny (mały)

## Architektura: OPCJA A (wszystko na Pi, samowystarczalne)
- LMS (Lyrion Music Server = "mózg") + Squeezelite (player) — oba na Pi

## Do zainstalowania
- **LMS + Squeezelite**: `dietpi-software install 35 36`
- **Shairport-Sync** (AirPlay) — przez `dietpi-software` (szukać po nazwie)
- **Avahi-Daemon** (discovery, wymagane dla AirPlay + LMS) — `dietpi-software`
- **Tailscale** — `dietpi-software` lub `curl -fsSL https://tailscale.com/install.sh | sh`
- **Spotify Connect (raspotify)**: `curl -sL https://dtcooper.github.io/raspotify/install.sh | sh`
- **Bluetooth A2DP** (bluez + bluealsa) — konfiguracja ręczna (patrz niżej)

## Konfiguracja LMS (http://<pi-ip>:9000)
- Settings → Manage Plugins:
  - włączyć **TIDAL local**, wyłączyć stare **TIDAL**
  - włączyć **Material Skin**
  - (opcjonalnie) **Radio Browser** dla radia internetowego
- Restart, potem Settings → Advanced → TIDAL → autoryzacja konta
- Squeezelite: ustawić wyjście `-o` na kartę DAC (`/etc/default/squeezelite`)

## Bluetooth A2DP (krok "fiddly")
- Włączyć adapter: `dietpi-config → Bluetooth`
- `apt install bluez-alsa-utils`
- Parowanie:
  bluetoothctl
  power on
  agent on
  default-agent
  scan on
  pair <MAC>
  trust <MAC>    # trust = auto-reconnect
  connect <MAC>
- Wyjście bluealsa skierować na kartę DAC

## Tailscale
- `tailscale up`, autoryzacja przez URL
- W panelu admina: wyłączyć key expiry dla tej maszyny (headless)

## Aplikacje sterujące (telefon)
- Tidal + radio: **Squeezer** (Android) / **iPeng** (iOS) lub Material web (:9000)
- Spotify: natywna apka Spotify
- AirPlay: natywnie
- YouTube Music / reszta: przez Bluetooth

## Świadome pominięcia
- Roon Bridge — nie
- Snapcast (multi-room) — nie
- FCast — odłożone (tylko odbiornik GUI/Electron, za ciężki na headless 512 MB;
  testować z Grayjay na laptopie/Androidzie)
- Docker / natywny Tidal Connect — nie (za ciężki na 512 MB; zamiast tego TIDAL local w LMS)
- Serwer biblioteki na Pi (Navidrome/Jellyfin) — nie (pliki są na zdalnym serwerze
  w Tailscale; do Pi grane przez Bluetooth z apki na telefonie)

## Uwagi z instrukcji InnoMaker
- Wyłączyć Wi-Fi hotspot; gniazda RCA/3.5mm łapią zakłócenia Wi-Fi
  (istotne przy współdzielonym radiu Zero 2 W — pamiętać przy strojeniu BT/Wi-Fi)

## Budżet RAM (opcja A, orientacyjnie idle)
- DietPi ~70 + LMS ~150 + Squeezelite ~8 + raspotify ~20 + shairport ~8
  + bluealsa ~8 + tailscale ~30 ≈ ~290 MB → zram jako zabezpieczenie