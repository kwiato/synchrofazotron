import { createContext } from 'preact';
import { useContext, useRef, useState } from 'preact/hooks';

// Brief centered notification, hoisted to app root so any view can fire one.
const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [text, setText] = useState('');
  const [show, setShow] = useState(false);
  const timer = useRef(null);

  const toast = (m) => {
    setText(m);
    setShow(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setShow(false), 4000);
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div class={'toast' + (show ? ' show' : '')}>{text}</div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
