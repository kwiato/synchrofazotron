// LAN device discovery for the Android shell. The Pi advertises a
// `_pistream._tcp` service over mDNS (avahi, see web/install.sh); here we watch
// for it and hand back a de-duplicated list of reachable panels. Native-only —
// the plugin is a no-op stub on the web, and the picker that uses this is gated
// behind IS_APP anyway.
import { ZeroConf } from 'capacitor-zeroconf';

const TYPE = '_pistream._tcp.';
const DOMAIN = 'local.';

// name -> { name, host, ip, port, url } ; keyed by service name so a device
// re-announcing (added -> resolved) updates in place instead of duplicating.
// Only a numeric IPv4 makes a usable row: Android's WebView cannot resolve
// .local names, and 'added' events carry no address yet (the plugin puts the
// service name in `hostname` there — an URL built from it can never work).
// Skipped entries appear once the service resolves; if it never does (Android
// NSD resolution is flaky with a VPN up), an empty list + manual entry beats
// a row that always fails.
function toDevice(service) {
  const ip = (service.ipv4Addresses || [])
    .find((a) => /^\d{1,3}(\.\d{1,3}){3}$/.test(a)) || '';
  if (!ip) return null;
  const port = service.port || 8787;
  return {
    name: service.name || ip,
    host: service.hostname || ip,
    ip,
    port,
    url: `http://${ip}:${port}`,
  };
}

// Start watching. `onChange(devicesArray)` fires whenever the set changes.
// Returns a stop() that tears the watch down.
export async function startDiscovery(onChange) {
  const found = new Map();
  const emit = () => onChange([...found.values()]);

  const handler = (result) => {
    const svc = result && result.service;
    if (!svc) return;
    if (result.action === 'removed') {
      if (svc.name) { found.delete(svc.name); emit(); }
      return;
    }
    // 'added' | 'resolved' — only usable once we have an address.
    const dev = toDevice(svc);
    if (dev) { found.set(dev.name, dev); emit(); }
  };

  await ZeroConf.watch({ type: TYPE, domain: DOMAIN }, handler);

  return async function stop() {
    try { await ZeroConf.unwatch({ type: TYPE, domain: DOMAIN }); } catch { /* already gone */ }
  };
}
