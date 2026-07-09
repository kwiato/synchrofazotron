import { useI18n } from '../../i18n.jsx';
import { AppearanceCard, AudioOutputCard } from './ConfigSection.jsx';
import { VisualizerCards } from './VisualizerSection.jsx';

// Look & feel: appearance & language, the visualizer, and audio output.
export function CustomizeSection() {
  const { t } = useI18n();
  return (
    <section class="active">
      <div class="sect-title">{t('nav_customize')}</div>
      <div class="cardgrid">
        <AppearanceCard />
        <VisualizerCards />
        <AudioOutputCard />
      </div>
    </section>
  );
}
