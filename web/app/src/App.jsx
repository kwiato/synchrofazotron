import { useState } from 'preact/hooks';
import { I18nProvider } from './i18n.jsx';
import { StatusProvider } from './status.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { Shell } from './Shell.jsx';
import { Connect } from './views/Connect.jsx';
import { IS_APP, apiBase } from './host.js';

export function App() {
  // In the app build, nothing can talk to a device until one is chosen, so the
  // providers (which fetch /api/i18n, /api/status) stay unmounted behind the
  // device picker. On the web IS_APP is false and this collapses to the panel
  // being served same-origin — unchanged behaviour.
  const [base, setBase] = useState(apiBase());
  if (IS_APP && !base) return <Connect onConnect={() => setBase(apiBase())} />;

  return (
    <I18nProvider>
      <ToastProvider>
        <StatusProvider>
          <Shell />
        </StatusProvider>
      </ToastProvider>
    </I18nProvider>
  );
}
