import { useI18n } from '../../i18n.jsx';
import { useVolumes } from '../../hooks.js';
import { VolumeSlider } from '../../components/VolumeSlider.jsx';
import { AppearanceCard, AudioOutputCard } from './ConfigSection.jsx';
import { VisualizerCards } from './VisualizerSection.jsx';

// Look & feel: appearance & language, the visualizer, per-source volume, and
// audio output.
export function CustomizeSection() {
  const { t } = useI18n();
  return (
    <section class="active">
      <div class="sect-title">{t('nav_customize')}</div>
      <div class="cardgrid">
        <AppearanceCard />
        <VisualizerCards />
        <VolumeCard />
        <AudioOutputCard />
      </div>
    </section>
  );
}

const VOL_ORDER = ['lms', 'airplay', 'bt'];
const VOL_LABELS = { lms: 'LMS', airplay: 'AirPlay', bt: 'Bluetooth' };

// Per-source volume — one slider per source that's controllable right now.
function VolumeCard() {
  const { t } = useI18n();
  const { volumes, setVolume } = useVolumes();
  const ids = VOL_ORDER.filter((id) => id in volumes);
  return (
    <div class="card">
      <h2><i class="ico ico-volume"></i> {t('vol_head')}</h2>
      {ids.length === 0
        ? <p class="muted">{t('vol_none')}</p>
        : ids.map((id) => (
            <VolumeSlider key={id} value={volumes[id]} label={VOL_LABELS[id]}
                          onInput={(v) => setVolume(id, v)} />
          ))}
    </div>
  );
}
