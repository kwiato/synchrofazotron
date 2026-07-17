package pl.synchrofazotron.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.launch
import pl.synchrofazotron.MainActivity
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.prefs.DeviceStore
import pl.synchrofazotron.ui.connect.ConnectScreen
import pl.synchrofazotron.ui.now.NowScreen
import pl.synchrofazotron.ui.settings.SettingsScreen
import pl.synchrofazotron.ui.studio.StudioScreen

private const val LOADING = " loading"

@Composable
fun App() {
    val context = LocalContext.current
    val store = remember { DeviceStore(context) }
    val scope = rememberCoroutineScope()

    // Sentinel initial value distinguishes "still reading DataStore" from
    // "read, and there is no saved device (null)".
    val baseUrl by store.baseUrl.collectAsStateWithLifecycle(initialValue = LOADING)

    when (val url = baseUrl) {
        LOADING -> Unit // brief blank frame while DataStore loads
        null -> ConnectScreen(onConnected = { scope.launch { store.setBaseUrl(it) } })
        else -> {
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
                        onChangeDevice = { scope.launch { store.clear() } },
                        onOpenSettings = { nav.navigate("settings") },
                    )
                }
                composable("settings") {
                    SettingsScreen(
                        session = session,
                        onBack = { nav.popBackStack() },
                        onOpenStudio = { nav.navigate("studio") },
                    )
                }
                composable("studio") {
                    StudioScreen(baseUrl = session.baseUrl, onBack = { nav.popBackStack() })
                }
            }
        }
    }
}
