import { useI18n } from '../../i18n.jsx';
import { CardHead } from '../../components/CardHead.jsx';
import { ConsoleLogo } from '../../components/ConsoleLogo.jsx';

const CREDITS = [
  ['🎚️', 'cava', 'https://github.com/karlstav/cava', 'Karl Stavestrand', 'https://github.com/karlstav'],
  ['🌈', 'glslViewer', 'https://github.com/patriciogonzalezvivo/glslViewer', 'Patricio Gonzalez Vivo', 'https://github.com/patriciogonzalezvivo'],
  ['🎧', 'Lyrion Music Server', 'https://github.com/LMS-Community/slimserver', 'LMS Community', 'https://github.com/LMS-Community'],
  ['🎨', 'Material Skin', 'https://github.com/CDrummond/lms-material', 'Craig Drummond', 'https://github.com/CDrummond'],
  ['▶️', 'squeezelite', 'https://github.com/ralph-irving/squeezelite', 'Ralph Irving', 'https://github.com/ralph-irving'],
  ['🍎', 'Shairport Sync', 'https://github.com/mikebrady/shairport-sync', 'Mike Brady', 'https://github.com/mikebrady'],
  ['📶', 'BlueALSA', 'https://github.com/arkq/bluez-alsa', 'Arkadiusz Bokowy', 'https://github.com/arkq'],
  ['🤝', 'bluez-tools', 'https://github.com/khvzak/bluez-tools', 'Alexander Orlenko', 'https://github.com/khvzak'],
  ['🐧', 'DietPi', 'https://github.com/MichaIng/DietPi', 'MichaIng', 'https://github.com/MichaIng'],
  ['🔗', 'Tailscale', 'https://github.com/tailscale/tailscale', null, null],
  ['🧮', 'NumPy', 'https://github.com/numpy/numpy', null, null],
  ['💡', 'Slimshader', 'https://github.com/ErikOostveen/Slimshader', 'Erik Oostveen', 'https://github.com/ErikOostveen'],
];

export function AboutSection() {
  const { t, repo, version } = useI18n();
  return (
    <section class="active">
      <div class="sect-title">{t('nav_about')}</div>
      <div class="cardgrid">
        <div class="card">
          <CardHead title="Synchrofazotron">
            {version && <span class="pill on" title={t('about_version')}>v{version}</span>}
          </CardHead>
          <ConsoleLogo />
          <p class="muted">{t('about_desc')}</p>
          <p class="muted">{t('about_repo')}</p>
          <a class="btn sec" href={`https://github.com/${repo}`} target="_blank" rel="noreferrer"
             style="text-align:center;text-decoration:none;">github.com/{repo}</a>
          <p class="muted small" style="margin-top:10px;">{t('about_license')}</p>
        </div>

        <div class="card">
          <h2>{t('about_head')}</h2>
          <p class="muted">{t('about_note')}</p>
          <div class="credits muted">
            {CREDITS.map(([emoji, name, url, author, authorUrl]) => (
              <div key={name}>
                {emoji} <a href={url} target="_blank" rel="noreferrer">{name}</a>
                {author && <> — <a href={authorUrl} target="_blank" rel="noreferrer">{author}</a></>}
              </div>))}
          </div>
        </div>
      </div>
    </section>
  );
}
