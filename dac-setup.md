# PiStream — przywrócenie audio przez DAC (do zrobienia gdy zadziała sprawny DAC)

> Stan na 2026-07-01: oryginalny InnoMaker DAC Mini HAT (PCM5122) **padł**
> (brak odpowiedzi na I2C `0x4d` na dwóch różnych Pi, LED zgasł — najpewniej
> ESD/zwarcie przy dotknięciu). Jako obejście PiStream gra teraz przez **HDMI audio**
> (jack w monitorze). Ten plik opisuje jak wrócić na DAC, gdy będzie sprawny egzemplarz.

## 0. Podmiana sprzętu
- Zamontować sprawny DAC HAT (równo, hammer-header dobrze dociśnięty, nie pod kątem).
- Sanity-check zanim ruszysz software:
  ```bash
  i2cdetect -y 1        # PCM5122 powinien pokazać się jako 4d (albo UU gdy driver zajął)
  ```
  Jeśli `4d`/`UU` się NIE pojawia — to dalej sprzęt/kontakt, nie ruszaj configu.

## 1. config.txt — przełączyć audio z HDMI na DAC
Plik: `/boot/firmware/config.txt` (backupy zmian z 2026-07-01 leżą obok jako `*.bak.*`).

Wyłączyć wbudowane audio i włączyć overlay DAC-a:
```ini
dtparam=audio=off            # było: on (dla HDMI); DAC wymaga off
#hdmi_drive=2                 # zbędne dla DAC (można zostawić, nie szkodzi)
#hdmi_force_hotplug=1         # jw.
dtoverlay=hifiberry-dacplus   # patrz uwaga o overlayu niżej
```

### ⚠️ Który overlay — do potwierdzenia na żywym DAC-u
- Plan (`plan.md`) wg instrukcji InnoMaker: `dtoverlay=allo-boss-dac-pcm512x-audio` (karta „BossDAC").
- Wcześniejsza próba `hifiberry-dacplus` też nie ożywiła chipa — ALE oba przypadki
  poległy tylko na `-121` (chip nie odpowiadał = martwy sprzęt), więc to **nie**
  rozstrzyga który overlay jest poprawny. Błędy `snd_soc_register_card ... -517`
  przy allo-boss to EPROBE_DEFER (normalne), nie oznaka złego overlaya.
- **Na sprawnym DAC-u przetestować oba** i zostawić ten, przy którym:
  `aplay -l` pokazuje kartę, `dmesg | grep pcm512` bez `-121`, dioda świeci.
  Kolejność prób: najpierw `allo-boss-dac-pcm512x-audio` (zgodnie z instrukcją),
  jak nie zadziała → `hifiberry-dacplus`.

## 2. Cofnąć obejście HDMI-audio (DietPi blokuje wbudowane audio i to nam pasuje dla DAC)
Przy DAC-u wbudowane `snd_bcm2835` nie jest potrzebne. Można przywrócić blacklistę:
```bash
# przywrócić oryginał (był backup):
mv /etc/modprobe.d/dietpi-disable_rpi_audio.conf.bak.* /etc/modprobe.d/dietpi-disable_rpi_audio.conf  # jeśli chcesz 1:1
# albo ręcznie odkomentować: blacklist snd_bcm2835
rm -f /etc/modules-load.d/hdmi-audio.conf       # usunąć wymuszone ładowanie HDMI audio
```
`/etc/asound.conf` (default card 0) zaktualizować na kartę DAC-a po sprawdzeniu jej numeru w `aplay -l`
(zwykle też będzie card 0 gdy HDMI audio wyłączone — potwierdzić).

## 3. Reboot i weryfikacja
```bash
reboot
# po restarcie:
aplay -l                      # oczekiwana karta DAC (BossDAC / sndrpihifiberry)
alsamixer                     # kontrolka Digital — podbić, unmute
speaker-test -c2 -twav        # test na DAC
```

## 4. Skierować odtwarzacze na DAC
- **Squeezelite**: `/etc/default/squeezelite` → parametr `-o` na kartę DAC
  (np. `SQUEEZELITE_OUTPUT_DEVICE=hw:CARD=sndrpihifiberry` — potwierdzić nazwą z `aplay -l`),
  potem `systemctl restart squeezelite`.
- **Shairport-Sync**: `/etc/shairport-sync.conf` → `alsa { output_device = "hw:0"; }` na kartę DAC.
- **Raspotify**: `/etc/raspotify/conf` → `LIBRESPOT_DEVICE` na kartę DAC.
- **bluealsa** (jeśli BT): przekierować wyjście na kartę DAC.

## 5. Uwaga z instrukcji InnoMaker
- Wyłączyć Wi-Fi hotspot / rozważyć Wi-Fi vs zakłócenia — gniazda RCA/3.5mm łapią szum Wi-Fi
  (istotne na współdzielonym radiu Zero 2 W).

---
### Log zmian zrobionych 2026-07-01 (obejście HDMI — do cofnięcia wg powyższego)
- `config.txt`: `audio=off→on`, `hdmi_blanking=1→0`, dodane `hdmi_drive=2`, `hdmi_force_hotplug=1`,
  zakomentowany `dtoverlay=hifiberry-dacplus`.
- `/etc/modprobe.d/dietpi-disable_rpi_audio.conf`: zakomentowany `blacklist snd_bcm2835`.
- Dodane `/etc/modules-load.d/hdmi-audio.conf` (`snd_bcm2835`).
- Dodane `/etc/asound.conf` (default card 0 = bcm2835 HDMI).
