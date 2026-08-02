package pl.synchrofazotron.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import pl.synchrofazotron.MainActivity
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.SETUP_BASE_URL
import pl.synchrofazotron.core.net.SetupModeDetector
import pl.synchrofazotron.core.prefs.DeviceStore
import pl.synchrofazotron.ui.components.Droplet
import pl.synchrofazotron.ui.components.Header
import pl.synchrofazotron.ui.components.PlayerBar
import pl.synchrofazotron.ui.connect.ConnectScreen
import pl.synchrofazotron.ui.panel.PanelScreen
import pl.synchrofazotron.ui.settings.SettingsScreen
import pl.synchrofazotron.ui.settings.SetupWifiScreen
import pl.synchrofazotron.ui.studio.StudioScreen
import pl.synchrofazotron.ui.theme.Spacing
import pl.synchrofazotron.ui.theme.SynchrofazotronTheme

private const val LOADING = " loading"

/** Root: applies the user's theme preference, then hosts the app. */
@Composable
fun AppRoot() {
    val context = LocalContext.current
    val store = remember { DeviceStore(context) }
    val theme by store.theme.collectAsStateWithLifecycle(initialValue = "system")
    SynchrofazotronTheme(pref = theme) { App() }
}

@Composable
fun App() {
    val context = LocalContext.current
    val store = remember { DeviceStore(context) }
    val scope = rememberCoroutineScope()
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

            val activity = context as? MainActivity
            DisposableEffect(session, activity) {
                activity?.volumeKeyHandler = { delta -> session.nudgeVolume(delta) }
                onDispose { activity?.volumeKeyHandler = null }
            }

            // Persistent shell: header + a single view slot + bottom player bar.
            // Saveable so a locale change (which recreates the activity) keeps you
            // on the same screen instead of bouncing back to the panel.
            var screen by rememberSaveable { mutableStateOf("panel") } // panel | settings | studio

            val notice by session.notice.collectAsStateWithLifecycle()
            Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
                Box(Modifier.fillMaxSize().padding(pad)) {
                    Column(Modifier.fillMaxSize()) {
                        Header(
                            session = session,
                            onHome = { screen = "panel" },
                            onToggleSettings = { screen = if (screen == "settings") "panel" else "settings" },
                            isSettings = screen == "settings",
                        )
                        Box(Modifier.weight(1f)) {
                            when (screen) {
                                "settings" -> SettingsScreen(
                                    session = session,
                                    onOpenStudio = { screen = "studio" },
                                    onChangeDevice = { picking = true },
                                )
                                "studio" -> StudioScreen(session.baseUrl, onBack = { screen = "settings" })
                                else -> PanelScreen(session, onOpenStudio = { screen = "studio" })
                            }
                        }
                        if (screen != "studio") {
                            PlayerBar(
                                session = session,
                                onHome = { screen = "panel" },
                                modifier = Modifier.padding(
                                    start = Spacing.xs,
                                    end = Spacing.xs,
                                    top = Spacing.xs2,
                                    bottom = Spacing.xs,
                                ),
                            )
                        }
                    }
                    Droplet(
                        text = notice,
                        modifier = Modifier.align(Alignment.TopCenter).padding(top = 52.dp),
                    )
                }
            }
        }
    }
}
