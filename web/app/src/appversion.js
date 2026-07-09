// Build identity, injected by CI at build time (see build-app.yml). Locally it
// is 'dev'. Used by the in-app updater to tell the installed build apart from
// the latest released one.
export const APP_SHA = import.meta.env.VITE_APP_SHA || 'dev';
export const APP_SHA_SHORT = APP_SHA.slice(0, 7);

const REPO = 'kwiato/synchrofazotron';
const REL = `https://github.com/${REPO}/releases/download/android-latest`;
export const APK_URL = `${REL}/app-debug.apk`;
export const VERSION_URL = `${REL}/version.json`;
