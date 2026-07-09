// Build identity, injected by CI at build time (see build-app.yml). Locally it
// is 'dev'. Used by the in-app updater to tell the installed build apart from
// the latest released one.
export const APP_SHA = import.meta.env.VITE_APP_SHA || 'dev';
export const APP_SHA_SHORT = APP_SHA.slice(0, 7);

const REPO = 'kwiato/synchrofazotron';
// APK download goes through a normal browser navigation (Browser.open), so the
// releases/download URL is fine there. The in-app *check* must use the GitHub
// API instead: release-asset URLs 302 to a host with no CORS header, which the
// WebView's fetch() blocks — the API sends Access-Control-Allow-Origin: *. The
// build SHA is published in the release body (see build-app.yml).
export const APK_URL = `https://github.com/${REPO}/releases/download/android-latest/app-debug.apk`;
export const RELEASE_API = `https://api.github.com/repos/${REPO}/releases/tags/android-latest`;
