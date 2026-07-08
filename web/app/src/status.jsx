import { createContext } from 'preact';
import { useCallback, useContext, useEffect, useState } from 'preact/hooks';
import { apiGet } from './api.js';

// One /api/status poll shared by the whole app (header pair countdown, player
// bar, now-playing) — same 3s cadence as the old panel, but a single request
// instead of the page re-fetching from several places.

const StatusContext = createContext({ status: null, refresh: () => {} });

export function StatusProvider({ children }) {
  const [status, setStatus] = useState(null);
  const refresh = useCallback(async () => {
    try { setStatus(await apiGet('/api/status')); } catch { /* keep last */ }
  }, []);
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);
  return (
    <StatusContext.Provider value={{ status, refresh }}>
      {children}
    </StatusContext.Provider>
  );
}

export const useStatus = () => useContext(StatusContext);
