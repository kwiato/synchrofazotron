package pl.synchrofazotron.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import pl.synchrofazotron.MainActivity
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.SETUP_BASE_URL
import pl.synchrofazotron.core.net.SetupModeDetector
import pl.synchrofazotron.core.prefs.DeviceStore
import pl.synchrofazotron.ui.connect.ConnectScreen
import pl.synchrofazotron.ui.now.NowScreen
import pl.synchrofazotron.ui.settings.SettingsScreen
import pl.synchrofazotron.ui.settings.SetupWifiScreen

private const val LOADING = " loading"

@Composable
fun App() {
    val context = LocalContext.current
    val store = remember { DeviceStore(context) }
    val scope = rememberCoroutineScope()

    // Sentinel initial value distinguishes "still reading DataStore" from
    // "read, and there is no saved device (null)".
    val baseUrl by store.baseUrl.collectAsStateWithLifecycle(initialValue = LOADING)

    // Setup-AP watch: when the phone is on Synchrofazotron-Setup (the device
    // lost its Wi-Fi and raised the fallback AP), take over with the Wi-Fi
    // setup screen — regardless of whether a device is saved, since that is
    // exactly the "took the device somewhere new" scenario.
    val detector = remember { SetupModeDetector(context) }
    DisposableEffect(detector) { onDispose { detector.close() } }
    var setupMode by remember { mutableStateOf(false) }
    var setupDismissed by remember { mutableStateOf(false) }
    LaunchedEffect(detector) {
        while (true) {
            val found = detector.probe()
            if (!found) setupDismissed = false // next AP encounter surfaces again
            setupMode = found
            delay(3_000)
        }
    }
    if (setupMode && !setupDismissed) {
        val session = remember { PanelSession(SETUP_BASE_URL) }
        DisposableEffect(session) {
            // The AP has no internet — without the bind, Android would keep
            // routing the panel calls over mobile data into the void.
            detector.bindToWifi()
            onDispose { detector.unbind(); session.close() }
        }
        SetupWifiScreen(session = session, onDismiss = { setupDismissed = true })
        return
    }

    // "Change device" opens the picker over the current device instead of
    // clearing it, so cancel can drop right back — mirrors the SPA's
    // switchDevice/prevBase flow.
    var picking by remember { mutableStateOf(false) }

    when (val url = baseUrl) {
        LOADING -> Unit // brief blank frame while DataStore loads
        null -> ConnectScreen(store = store, onConnected = { scope.launch { store.setBaseUrl(it) } })
        else -> {
            if (picking) {
                ConnectScreen(
                    store = store,
                    onConnected = { scope.launch { store.setBaseUrl(it) }; picking = false },
                    onCancel = { picking = false },
                )
                return
            }
            val session = remember(url) { PanelSession(url) }
            DisposableEffect(session) { onDispose { session.close() } }

            // Bridge the phone's hardware volume keys to the device volume.
            val activity = context as? MainActivity
            DisposableEffect(session, activity) {
                activity?.volumeKeyHandler = { delta -> session.nudgeVolume(delta) }
                onDispose { activity?.volumeKeyHandler = null }
            }

            val nav = rememberNavController()
            NavHost(navController = nav, startDestination = "now") {
                composable("now") {
                    NowScreen(
                        session = session,
                        onChangeDevice = { picking = true },
                        onOpenSettings = { nav.navigate("settings") },
                    )
                }
                composable("settings") {
                    SettingsScreen(session = session, onBack = { nav.popBackStack() })
                }
            }
        }
    }
}
