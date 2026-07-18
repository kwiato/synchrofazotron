package pl.synchrofazotron.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import pl.synchrofazotron.MainActivity
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.prefs.DeviceStore
import pl.synchrofazotron.ui.components.Header
import pl.synchrofazotron.ui.components.PlayerBar
import pl.synchrofazotron.ui.connect.ConnectScreen
import pl.synchrofazotron.ui.panel.PanelScreen
import pl.synchrofazotron.ui.settings.SettingsScreen
import pl.synchrofazotron.ui.studio.StudioScreen

private const val LOADING = " loading"

@Composable
fun App() {
    val context = LocalContext.current
    val store = remember { DeviceStore(context) }
    val scope = rememberCoroutineScope()
    val baseUrl by store.baseUrl.collectAsStateWithLifecycle(initialValue = LOADING)

    when (val url = baseUrl) {
        LOADING -> Unit
        null -> ConnectScreen(onConnected = { scope.launch { store.setBaseUrl(it) } })
        else -> {
            val session = remember(url) { PanelSession(url) }
            DisposableEffect(session) { onDispose { session.close() } }

            val activity = context as? MainActivity
            DisposableEffect(session, activity) {
                activity?.volumeKeyHandler = { delta -> session.nudgeVolume(delta) }
                onDispose { activity?.volumeKeyHandler = null }
            }

            // Persistent shell: header + a single view slot + bottom player bar.
            var screen by remember { mutableStateOf("panel") } // panel | settings | studio

            Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
                Column(Modifier.fillMaxSize().padding(pad)) {
                    Header(
                        session = session,
                        onHome = { screen = "panel" },
                        onToggleSettings = { screen = if (screen == "settings") "panel" else "settings" },
                        isSettings = screen == "settings",
                    )
                    HorizontalDivider()
                    Box(Modifier.weight(1f)) {
                        when (screen) {
                            "settings" -> SettingsScreen(
                                session = session,
                                onOpenStudio = { screen = "studio" },
                                onChangeDevice = { scope.launch { store.clear() } },
                            )
                            "studio" -> StudioScreen(session.baseUrl, onBack = { screen = "settings" })
                            else -> PanelScreen(session, onOpenStudio = { screen = "studio" })
                        }
                    }
                    if (screen != "studio") {
                        PlayerBar(
                            session = session,
                            onHome = { screen = "panel" },
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                        )
                    }
                }
            }
        }
    }
}
