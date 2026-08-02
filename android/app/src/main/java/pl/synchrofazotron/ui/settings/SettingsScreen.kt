package pl.synchrofazotron.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import android.os.SystemClock
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Speaker
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.BtDevice
import pl.synchrofazotron.core.net.BtInfo
import pl.synchrofazotron.core.net.WifiInfo
import pl.synchrofazotron.core.net.WifiNetwork

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(session: PanelSession, onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back))
                    }
                },
            )
        },
    ) { pad ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(pad)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            DeviceCard(session)
            WifiCard(session)
            BluetoothCard(session)
            Column(Modifier.padding(bottom = 24.dp)) {}
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector? = null,
    content: @Composable () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (icon != null) {
                    Icon(icon, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                }
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Column(Modifier.padding(top = 12.dp)) { content() }
        }
    }
}

// Device: broadcast name with a pencil that opens the rename dialog, plus a
// ping button — the simplest possible "is it alive" probe (health + latency).
@Composable
private fun DeviceCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    val status by session.status.collectAsStateWithLifecycle()
    var renaming by remember { mutableStateOf(false) }
    var renameMsg by remember { mutableStateOf<String?>(null) }
    var pinging by remember { mutableStateOf(false) }
    var ping by remember { mutableStateOf<Pair<Boolean, Long>?>(null) }

    SectionCard(stringResource(R.string.device_head), icon = Icons.Filled.Speaker) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = status?.deviceName.orEmpty().ifBlank { "…" },
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = { renaming = true }) {
                Icon(Icons.Filled.Edit, stringResource(R.string.name_edit))
            }
        }
        OutlinedButton(
            enabled = !pinging,
            onClick = {
                scope.launch {
                    pinging = true
                    val t0 = SystemClock.elapsedRealtime()
                    val ok = session.ping() == true
                    ping = ok to (SystemClock.elapsedRealtime() - t0)
                    pinging = false
                }
            },
            modifier = Modifier.padding(top = 8.dp),
        ) {
            if (pinging) {
                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.padding(end = 8.dp).size(16.dp),
                )
            }
            Text(stringResource(R.string.ping))
        }
        ping?.let { (ok, ms) ->
            Text(
                text = if (ok) stringResource(R.string.ping_ok, ms)
                       else stringResource(R.string.ping_fail),
                style = MaterialTheme.typography.bodySmall,
                color = if (ok) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        renameMsg?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }

    if (renaming) {
        var newName by remember { mutableStateOf(status?.deviceName.orEmpty()) }
        var busy by remember { mutableStateOf(false) }
        AlertDialog(
            onDismissRequest = { if (!busy) renaming = false },
            title = { Text(stringResource(R.string.name_edit)) },
            text = {
                Column {
                    Text(
                        text = stringResource(R.string.name_note),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    OutlinedTextField(
                        value = newName,
                        onValueChange = { newName = it.take(32) },
                        singleLine = true,
                        enabled = !busy,
                        label = { Text(stringResource(R.string.name_label)) },
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !busy && newName.isNotBlank(),
                    onClick = {
                        scope.launch {
                            busy = true
                            val res = session.rename(newName.trim())
                            renameMsg = res?.message
                            busy = false
                            renaming = false
                        }
                    },
                ) { Text(stringResource(R.string.save)) }
            },
            dismissButton = {
                TextButton(enabled = !busy, onClick = { renaming = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@Composable
internal fun WifiCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var info by remember { mutableStateOf<WifiInfo?>(null) }
    var ssid by remember { mutableStateOf("") }
    var key by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var scanning by remember { mutableStateOf(false) }
    var scanned by remember { mutableStateOf<List<WifiNetwork>>(emptyList()) }

    suspend fun reload() { info = session.fetchWifi() }
    LaunchedEffect(session) { reload() }

    SectionCard(stringResource(R.string.wifi_head), icon = Icons.Filled.Wifi) {
        val cur = info?.current
        Text(
            text = if (cur != null && cur.ssid.isNotBlank())
                stringResource(R.string.wifi_current, cur.ssid)
            else stringResource(R.string.wifi_not_connected),
            style = MaterialTheme.typography.bodyMedium,
        )

        Text(
            text = stringResource(R.string.wifi_saved),
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.padding(top = 16.dp, bottom = 4.dp),
        )
        val saved = info?.saved.orEmpty()
        if (saved.isEmpty()) {
            Text(stringResource(R.string.wifi_no_saved), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            saved.forEach { net ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(net.ssid, modifier = Modifier.weight(1f))
                    val isCurrent = cur?.ssid == net.ssid
                    if (!isCurrent) {
                        TextButton(
                            enabled = !busy,
                            onClick = {
                                scope.launch { busy = true; session.removeWifi(net.slot); reload(); busy = false }
                            },
                        ) { Text(stringResource(R.string.wifi_remove)) }
                    }
                }
            }
        }

        Text(
            text = stringResource(R.string.wifi_add),
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.padding(top = 16.dp, bottom = 4.dp),
        )
        OutlinedTextField(
            value = ssid, onValueChange = { ssid = it }, singleLine = true,
            label = { Text(stringResource(R.string.wifi_ssid)) },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = key, onValueChange = { key = it }, singleLine = true,
            label = { Text(stringResource(R.string.wifi_key)) },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = !busy && ssid.isNotBlank(),
                onClick = {
                    scope.launch { busy = true; session.addWifi(ssid.trim(), key); ssid = ""; key = ""; reload(); busy = false }
                },
            ) { Text(stringResource(R.string.wifi_save)) }
            OutlinedButton(
                enabled = !scanning,
                onClick = {
                    scope.launch {
                        scanning = true
                        scanned = session.scanWifi()?.networks.orEmpty()
                        scanning = false
                    }
                },
            ) {
                if (scanning) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.padding(end = 8.dp).size(16.dp))
                    Text(stringResource(R.string.wifi_scanning))
                } else Text(stringResource(R.string.wifi_scan))
            }
        }
        scanned.forEach { net ->
            TextButton(onClick = { ssid = net.ssid }, modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth()) {
                    Text(net.ssid, Modifier.weight(1f))
                    Text("${net.signal} dBm", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun BluetoothCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    val status by session.status.collectAsStateWithLifecycle()
    var bt by remember { mutableStateOf<BtInfo?>(null) }
    var busyMac by remember { mutableStateOf<String?>(null) }

    suspend fun reload() { bt = session.fetchBt() }
    LaunchedEffect(session) { reload() }

    SectionCard(stringResource(R.string.bt_head), icon = Icons.Filled.Bluetooth) {
        val secs = status?.pairSecondsLeft ?: 0
        Button(
            onClick = { scope.launch { session.pair() } },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(stringResource(R.string.bt_pair)) }
        if (secs > 0) {
            Text(
                text = stringResource(R.string.bt_pairing_active, secs),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        val paired = bt?.paired.orEmpty()
        if (paired.isEmpty()) {
            Text(
                stringResource(R.string.bt_none),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 12.dp),
            )
        } else {
            paired.forEachIndexed { i, d ->
                if (i > 0) HorizontalDivider(Modifier.padding(vertical = 4.dp))
                BtRow(
                    device = d,
                    busy = busyMac == d.mac,
                    onConnect = { scope.launch { busyMac = d.mac; session.btConnect(d.mac); reload(); busyMac = null } },
                    onDisconnect = { scope.launch { busyMac = d.mac; session.btDisconnect(d.mac); reload(); busyMac = null } },
                    onForget = { scope.launch { busyMac = d.mac; session.btForget(d.mac); reload(); busyMac = null } },
                )
            }
        }
    }
}

@Composable
private fun BtRow(
    device: BtDevice,
    busy: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onForget: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(device.name.ifBlank { device.mac }, style = MaterialTheme.typography.bodyLarge)
            if (device.connected) {
                Text(stringResource(R.string.bt_connected), style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary)
            }
        }
        if (busy) {
            CircularProgressIndicator(strokeWidth = 2.dp)
        } else if (device.connected) {
            TextButton(onClick = onDisconnect) { Text(stringResource(R.string.bt_disconnect)) }
        } else {
            TextButton(onClick = onForget) { Text(stringResource(R.string.bt_forget)) }
            Button(onClick = onConnect) { Text(stringResource(R.string.bt_connect)) }
        }
    }
}
