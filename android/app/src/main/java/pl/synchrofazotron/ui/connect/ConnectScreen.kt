package pl.synchrofazotron.ui.connect

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pl.synchrofazotron.R
import pl.synchrofazotron.core.net.PanelClient
import pl.synchrofazotron.core.net.PanelDiscovery
import pl.synchrofazotron.core.net.normalizeBaseUrl
import pl.synchrofazotron.core.prefs.DeviceStore

/**
 * Device picker — mirror of the SPA's Connect view: saved devices, devices
 * discovered over mDNS, and manual entry, in that order. [onCancel] is set
 * when the picker was opened from "change device", so backing out restores
 * the previous device instead of stranding the user.
 */
@Composable
fun ConnectScreen(
    store: DeviceStore,
    onConnected: (String) -> Unit,
    onCancel: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    var host by remember { mutableStateOf("") }
    var checking by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val known by store.knownDevices.collectAsStateWithLifecycle(initialValue = emptyList())
    val discovery = remember { PanelDiscovery(context) }
    val discovered by discovery.watch().collectAsStateWithLifecycle(initialValue = emptyList())
    // a discovered device already on the saved list would render twice
    val fresh = discovered.filter { d -> known.none { it.url == d.url } }

    fun attempt(url: String, fallbackName: String) {
        if (checking) return
        error = false
        checking = true
        scope.launch {
            val name = withContext(Dispatchers.IO) {
                val c = PanelClient(url)
                try {
                    if (c.health()) c.deviceName() ?: fallbackName else null
                } finally {
                    c.close()
                }
            }
            checking = false
            if (name != null) {
                store.rememberDevice(name, url)
                onConnected(url)
            } else {
                error = true
            }
        }
    }

    fun attemptManual() {
        if (host.isBlank()) return
        val url = normalizeBaseUrl(host)
        attempt(url, host.trim())
    }

    Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(pad)
                .padding(horizontal = 24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = stringResource(R.string.connect_title),
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 24.dp),
            )

            if (known.isNotEmpty()) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            text = stringResource(R.string.connect_saved),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        known.forEach { d ->
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                TextButton(
                                    enabled = !checking,
                                    onClick = { attempt(d.url, d.name) },
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                        Text(d.name, fontWeight = FontWeight.SemiBold)
                                        Text(
                                            text = d.url.removePrefix("http://"),
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.padding(start = 8.dp),
                                        )
                                    }
                                }
                                IconButton(onClick = { scope.launch { store.forgetDevice(d.url) } }) {
                                    Icon(
                                        Icons.Filled.Close,
                                        contentDescription = stringResource(R.string.connect_remove),
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    if (fresh.isEmpty()) {
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 12.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Icon(
                                Icons.Filled.Wifi,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                text = stringResource(R.string.connect_searching),
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.padding(top = 8.dp),
                            )
                            Text(
                                text = stringResource(R.string.connect_none),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(top = 4.dp),
                            )
                        }
                    } else {
                        fresh.forEach { d ->
                            TextButton(
                                enabled = !checking,
                                onClick = { attempt(d.url, d.name) },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                    Text(d.name, fontWeight = FontWeight.SemiBold)
                                    Text(
                                        text = "${d.ip}:${d.port}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(start = 8.dp),
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Text(
                text = stringResource(R.string.connect_manual),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = host,
                onValueChange = { host = it; error = false },
                label = { Text(stringResource(R.string.connect_host_label)) },
                placeholder = { Text(stringResource(R.string.connect_host_hint)) },
                singleLine = true,
                enabled = !checking,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(onGo = { attemptManual() }),
                modifier = Modifier.fillMaxWidth(),
            )
            if (error) {
                Text(
                    text = stringResource(R.string.connect_unreachable),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Button(
                onClick = { attemptManual() },
                enabled = !checking && host.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (checking) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier
                            .padding(end = 8.dp)
                            .size(18.dp),
                    )
                    Text(stringResource(R.string.connect_checking))
                } else {
                    Text(stringResource(R.string.connect_button))
                }
            }

            if (onCancel != null) {
                TextButton(
                    onClick = onCancel,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 16.dp),
                ) { Text(stringResource(R.string.connect_cancel)) }
            } else {
                Column(Modifier.padding(bottom = 16.dp)) {}
            }
        }
    }
}
