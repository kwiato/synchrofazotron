# PiStream control panel

Lekki mikroserwis (Python, tylko biblioteka standardowa — bez zależności) serwujący
mobilną stronę HTML do sterowania odtwarzaczem audio PiStream. Pomyślany do wystawienia
przez Tailscale.

## Co robi

- **Przycisk „Włącz parowanie Bluetooth"** — ustawia adapter jako `discoverable` i
  `pairable` na 180 s. Auto-akceptacją parowania („Just Works", bez potwierdzania po
  stronie Pi) zajmuje się osobna trwała usługa **`bt-agent -c NoInputNoOutput`**
  (pakiet `bluez-tools`, instalowany przez `install.sh`). Panel dodatkowo nadaje
  `trust` połączonym urządzeniom, żeby wracały automatycznie.
- **Instrukcje** jak i co odtwarzać: Bluetooth, Spotify Connect, AirPlay,
  TIDAL/radio/biblioteka przez Lyrion Music Server.
- Podgląd statusu na żywo (BT gotowy/parowanie, połączone urządzenia, stan usług).
- **„Teraz gra"** — które źródła aktualnie grają (LMS via jsonrpc, Bluetooth via
  `bluealsa-cli`, AirPlay/Spotify via zajętość ALSA) + ostrzeżenie gdy gra kilka naraz.
- **Przyciski play/pause** per źródło (po prawej):
  - **LMS** — jsonrpc,
  - **Bluetooth** — AVRCP przez BlueZ `MediaPlayer1` (pauzuje telefon-źródło),
  - **AirPlay** — MPRIS (`org.mpris.MediaPlayer2.ShairportSync`),
  - **Spotify** — brak sterowania lokalnego (librespot); pauzuj z apki Spotify.

## Instalacja i aktualizacja (na Pi)

Prosto z GitHuba (instalacja i update to to samo polecenie — pobiera najnowszą
wersję i restartuje usługi):

```bash
curl -fsSL https://raw.githubusercontent.com/__REPO__/main/web/install.sh | sudo bash
```

Albo lokalnie (pliki skopiowane na Pi):

```bash
sudo bash install.sh
```

Panel wystartuje jako usługa `pistream-panel` (autostart przy boot) na porcie **8787**.

Dostęp:
- Tailscale: `http://<tailscale-ip>:8787` lub `http://pistream:8787` (MagicDNS)
- LAN: `http://<ip-lan>:8787`

## Konfiguracja

Wszystko przez zmienne środowiskowe (ustawiane w `pistream-panel.service`),
z sensownymi domyślnymi:

| Env | Domyślnie | Opis |
|---|---|---|
| `PISTREAM_NAME` | hostname | nazwa urządzenia pokazywana w panelu |
| `PISTREAM_LMS_PLAYER` | hostname | nazwa playera Squeezelite w LMS |
| `PISTREAM_SPOTIFY` | `0` | `1` = pokaż sekcję Spotify (gdy raspotify zainstalowany) |
| `PISTREAM_WIFI_IFACE` | `wlan0` | interfejs Wi-Fi dla strony ustawień |
| `PISTREAM_PANEL_PORT` | `8787` | port HTTP |
| `PISTREAM_PANEL_BIND` | `0.0.0.0` | adres bind |

## Endpointy

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/` | strona panelu |
| GET | `/settings` | strona ustawień (Wi-Fi) |
| GET | `/api/status` | JSON: stan BT, połączone urządzenia, aktywne źródła, usługi |
| GET | `/api/wifi` | JSON: bieżące połączenie + zapisane sieci (bez haseł) |
| GET | `/api/wifi/scan` | JSON: sieci w zasięgu |
| POST | `/api/pair` | włącza okno parowania BT |
| POST | `/api/control` | `{"source":"lms\|bt\|airplay","action":"toggle\|play\|pause"}` |
| POST | `/api/wifi/add` | `{"ssid":"...","key":"..."}` — zapis do bazy DietPi + reload |
| POST | `/api/wifi/remove` | `{"slot":n}` — usunięcie (bieżąca sieć zablokowana) |

## Ustawienia Wi-Fi — jak działa

Strona `/settings` zapisuje sieci do bazy DietPi (`/var/lib/dietpi/dietpi-wifi.db`,
te same sloty co `dietpi-config`), regeneruje `wpa_supplicant.conf` przez
`dietpi-wifidb 1` i przeładowuje konfigurację w locie (`wpa_cli reconfigure`) —
bez restartu i bez zrywania bieżącego połączenia. Można dodać sieć spoza zasięgu
(np. domową przed przewiezieniem urządzenia).

## Uwagi

- Usługa działa jako **root** (wymagane przez `bluetoothctl` do sterowania agentem
  i widocznością). Dźwięk z BT trafia na wyjście ALSA `default` przez `bluealsa-aplay`.
- Wystawiaj panel przez **Tailscale**, nie do publicznego internetu — endpointy nie mają
  autoryzacji, a `/api/wifi/add` przyjmuje hasła sieci (w tailnecie ruch jest szyfrowany;
  w otwartym internecie byłby to plain HTTP).
- Sekcja Spotify jest domyślnie ukryta (`PISTREAM_SPOTIFY=0`) — raspotify świadomie
  pominięty w instalacji 2026-07.
- Dźwięk wychodzi przez DAC (BossDAC, overlay `allo-boss-dac-pcm512x-audio`);
  historia obejścia HDMI w `../dac-setup.md`.
