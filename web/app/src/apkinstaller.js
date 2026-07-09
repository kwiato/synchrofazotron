// Bridge to the native APK self-updater (ApkInstallerPlugin.java, Android shell
// only). Downloading via the system browser stalled at 100% on Play Protect's
// download scan, so the native side fetches the APK itself and hands it to the
// package installer. On the web build every call rejects ("not implemented") —
// callers are gated by IS_APP anyway.
import { registerPlugin } from '@capacitor/core';

export const ApkInstaller = registerPlugin('ApkInstaller');
