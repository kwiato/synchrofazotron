import { I18nProvider } from './i18n.jsx';
import { StatusProvider } from './status.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { Shell } from './Shell.jsx';

export function App() {
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
