# PiStream visualizer — słupki cava na HDMI

"Fajerwerki na specjalną okazję": gdy do Pi jest wpięty HDMI, na ekranie tańczą
słupki [cava](https://github.com/karlstav/cava) w rytm tego, co aktualnie gra
(LMS, AirPlay, Bluetooth). Gdy HDMI wypięte — wizualizer nie działa i nie zużywa
zasobów. Muzyka gra identycznie w obu przypadkach.

## Architektura

```
źródła (squeezelite / shairport / bluealsa-aplay)
   └─> pcm "pistream"  (ALSA: plug -> route -> multi)
         ├─> hw:BossDAC          (dźwięk — zawsze)
         └─> hw:Loopback,0,0     (kopia strumienia — snd-aloop)
                └─> plughw:Loopback,1,0  <- czyta cava (tylko gdy HDMI wpięte)
```

- **Tor audio jest stały** — o wpięciu HDMI decyduje tylko to, czy działa cava.
  Dzięki temu wpinanie/wypinanie kabla nigdy nie przerywa muzyki. (Dynamiczne
  przepinanie toru wymagałoby restartu odtwarzaczy przy każdym hotplugu, bo
  libasound czyta konfigurację raz na start procesu.)
- **`pistream-hdmi-watch`** co 5 s sprawdza `/sys/class/drm/*-HDMI-*/status`
  i startuje/zatrzymuje `pistream-visualizer` (cava na `tty1`).
- Koszt stały: znikomy CPU na kopiowanie sampli; tor przechodzi przez `plug`,
  więc formalnie przestaje być bit-perfect (w praktyce niesłyszalne).

## Instalacja / aktualizacja

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/install.sh | sudo bash
```

Skrypt robi backupy zmienianych configów (`*.bak.<data>`). Pełny powrót do
toru bezpośredniego:

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/uninstall.sh | sudo bash
```

## Sterowanie ręczne

```bash
systemctl start|stop pistream-visualizer     # ręczne fajerwerki
systemctl stop pistream-hdmi-watch           # wyłącz automat (do restartu)
# konsola logowania na HDMI zamiast wizualizera:
systemctl stop pistream-hdmi-watch pistream-visualizer && systemctl start getty@tty1
```

Wizualizer zajmuje `tty1`; konsole tekstowe nadal dostępne na Alt+F2…F6.

## Diagnostyka

- **Słupki stoją mimo muzyki** — sprawdź, czy źródło faktycznie gra przez
  `pistream`: `grep -o '\-o [^ ]*' /etc/default/squeezelite` (i analogicznie
  shairport/bluealsa). Po instalacji źródła wymagają restartu (skrypt to robi).
- **Test pętli bez HDMI**: puść muzykę i
  `arecord -D plughw:Loopback,1,0 -f S16_LE -d 1 /tmp/t.wav` — plik powinien
  zawierać dźwięk, nie ciszę.
- **Watcher kończy pracę od razu** — kernel bez KMS nie wystawia statusu DRM;
  wtedy zostaje sterowanie ręczne (patrz wyżej).
- **cava wygląda blado** — konsola linuksowa ma ubogą paletę; kolory/gradienty
  można stroić w `/opt/pistream-visualizer/cava.conf` (sekcja `[color]`),
  po zmianie `systemctl restart pistream-visualizer`.

## Pliki

| Plik | Trafia do | Rola |
|---|---|---|
| `asound-tee.conf` | blok w `/etc/asound.conf` | urządzenie `pistream` (DAC+pętla) |
| `cava.conf` | `/opt/pistream-visualizer/` | konfiguracja wizualizera |
| `hdmi-watch.sh` | `/opt/pistream-visualizer/` | pętla hotplug HDMI |
| `pistream-visualizer.service` | `/etc/systemd/system/` | cava na tty1 |
| `pistream-hdmi-watch.service` | `/etc/systemd/system/` | watcher (enabled) |
