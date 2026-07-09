import { createContext } from 'preact';
import { useContext, useRef, useState } from 'preact/hooks';

// Brief notification pinned to the top, hoisted to app root so any view can fire
// one. toast(text) is the simple 4 s flash; toast(text, opts) takes
//   { tone: 'good'|'warn'|'danger', spinner: true, sticky: true, duration: ms }
// Calling it again replaces the same toast — e.g. a sticky spinner "Updating…"
// that later resolves to a green check and auto-dismisses.
const ToastContext = createContext(() => {});

const CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 L10 18 L20 6"/></svg>';

export function ToastProvider({ children }) {
  const [st, setSt] = useState({ text: '', tone: '', spinner: false });
  const [show, setShow] = useState(false);
  const timer = useRef(null);

  const toast = (text, opts = {}) => {
    setSt({ text, tone: opts.tone || '', spinner: !!opts.spinner });
    setShow(true);
    clearTimeout(timer.current);
    if (!opts.sticky) {
      timer.current = setTimeout(() => setShow(false), opts.duration || 4000);
    }
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div class={'toast' + (show ? ' show' : '') + (st.tone ? ' ' + st.tone : '')}>
        {st.spinner && <span class="spinner"></span>}
        {!st.spinner && st.tone === 'good'
          && <span class="toast-ico" dangerouslySetInnerHTML={{ __html: CHECK }} />}
        <span>{st.text}</span>
      </div>
    </ToastContext.Provider>
  );
}

// Inline variant — the same pill, but it flows in the DOM (under whatever fired
// it) instead of floating at the top. Mount it when there's something to say;
// it animates itself in. Key it by the message to replay the animation.
export function InlineToast({ tone, children }) {
  return (
    <div class={'toast toast-inline' + (tone ? ' ' + tone : '')}>
      {tone === 'good' && <span class="toast-ico" dangerouslySetInnerHTML={{ __html: CHECK }} />}
      <span>{children}</span>
    </div>
  );
}

export const useToast = () => useContext(ToastContext);
