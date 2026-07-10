// App-update logic shared by the Settings card (ConfigSection) and the device
// picker's escape hatch (Connect) — the latter exists because the Settings
// route needs a connected device, which is unreachable exactly when a broken
// build blocks connecting.
import { Browser } from '@capacitor/browser';
import { ApkInstaller } from './apkinstaller.js';
import { APK_URL, APP_SHA_SHORT, RELEASE_API } from './appversion.js';

// true = a newer build exists, false = up to date, null = the check failed.
// The GitHub API (not the release-asset URL) because the WebView's fetch needs
// CORS headers; the build SHA is published in the release body (build-app.yml).
export async function appUpdateAvailable() {
  try {
    const r = await fetch(`${RELEASE_API}?_=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) return null;
    const m = ((await r.json()).body || '').match(/[0-9a-f]{7,40}/i);
    const latest = m ? m[0].slice(0, 7) : '';
    return !!latest && latest !== APP_SHA_SHORT;
  } catch { return null; }
}

// Downloads the APK natively and fires the system installer. Progress goes
// through onState(state, pct): 'allow' (the one-time "install unknown apps"
// grant is missing; the system settings screen was opened — tap again after),
// 'downloading' (pct when the size is known), 'installing', or 'fallback'
// (native path failed / web build — the APK was opened in the browser).
export async function installAppUpdate(onState) {
  let sub = null;
  try {
    if (!(await ApkInstaller.canInstall()).allowed) {
      onState('allow');
      await ApkInstaller.openInstallSettings();
      return;
    }
    onState('downloading');
    sub = await ApkInstaller.addListener('progress', ({ received, total }) => {
      onState('downloading', total > 0 ? Math.round((received / total) * 100) : null);
    });
    await ApkInstaller.downloadAndInstall({ url: APK_URL });
    onState('installing');
  } catch {
    onState('fallback');
    try { await Browser.open({ url: APK_URL }); } catch { /* ignore */ }
  } finally {
    if (sub) sub.remove();
  }
}
