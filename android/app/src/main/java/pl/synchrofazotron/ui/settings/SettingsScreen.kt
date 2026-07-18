package pl.synchrofazotron.ui.settings

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Android
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Speaker
import androidx.compose.material.icons.filled.SystemUpdate
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.VolumeUp
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.update.AppUpdater
import pl.synchrofazotron.ui.components.SegTabs
import pl.synchrofazotron.core.net.AudioState
import pl.synchrofazotron.core.net.BtDevice
import pl.synchrofazotron.core.net.BtInfo
import pl.synchrofazotron.core.net.TailscaleState
import pl.synchrofazotron.core.net.TidalState
import pl.synchrofazotron.core.net.VizState
import pl.synchrofazotron.core.net.WifiInfo
import pl.synchrofazotron.core.net.WifiNetwork

@Composable
fun SettingsScreen(session: PanelSession, onOpenStudio: () -> Unit, onChangeDevice: () -> Unit) {
    val sections = listOf(
        "customize" to stringResource(R.string.nav_customize),
        "connections" to stringResource(R.string.nav_connections),
        "config" to stringResource(R.string.nav_config),
        "about" to stringResource(R.string.nav_about),
    )
    var sec by remember { mutableStateOf("config") }

    Column(Modifier.fillMaxSize()) {
        SegTabs(
            items = sections,
            active = sec,
            onChange = { sec = it },
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            when (sec) {
                "customize" -> {
                    VolumeCard(session)
                    AudioCard(session)
                }
                "connections" -> {
                    WifiCard(session)
                    BluetoothCard(session)
                    TidalCard(session)
                }
                "config" -> {
                    DeviceCard(session, onChangeDevice)
                    TailscaleCard(session)
                    UpdateCard(session)
                    AppUpdateCard()
                }
                else -> AboutCard(session)
            }
            Column(Modifier.padding(bottom = 24.dp)) {}
        }
    }
}

@Composable
private fun SectionCard(icon: ImageVector, title: String, content: @Composable () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Column(Modifier.padding(top = 12.dp)) { content() }
        }
    }
}

@Composable
private fun WifiCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var info by remember { mutableStateOf<WifiInfo?>(null) }
    var ssid by remember { mutableStateOf("") }
    var key by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var scanning by remember { mutableStateOf(false) }
    var scanned by remember { mutableStateOf<List<WifiNetwork>>(emptyList()) }

    suspend fun reload() { info = session.fetchWifi() }
    LaunchedEffect(session) { reload() }

    SectionCard(Icons.Filled.Wifi, stringResource(R.string.wifi_head)) {
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
                } else {
                    Icon(Icons.Filled.Search, null, Modifier.padding(end = 8.dp).size(18.dp))
                    Text(stringResource(R.string.wifi_scan))
                }
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

    SectionCard(Icons.Filled.Bluetooth, stringResource(R.string.bt_head)) {
        val secs = status?.pairSecondsLeft ?: 0
        Button(
            onClick = { scope.launch { session.pair() } },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Icon(Icons.Filled.Bluetooth, null, Modifier.padding(end = 8.dp).size(18.dp))
            Text(stringResource(R.string.bt_pair))
        }
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

private fun openUrl(context: Context, url: String) {
    runCatching {
        context.startActivity(
            Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }
}

@Composable
private fun TidalCard(session: PanelSession) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var tidal by remember { mutableStateOf<TidalState?>(null) }
    var busy by remember { mutableStateOf(false) }
    var authCode by remember { mutableStateOf<String?>(null) }
    var authLink by remember { mutableStateOf<String?>(null) }
    var awaiting by remember { mutableStateOf(false) }

    suspend fun reload() { tidal = session.tidal() }
    LaunchedEffect(session) { reload() }

    SectionCard(Icons.Filled.LibraryMusic, stringResource(R.string.tidal_head)) {
        val t = tidal
        if (t == null) {
            CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
            return@SectionCard
        }
        val enabled = t.pluginState == "enabled" || t.available

        if (!enabled) {
            if (t.installing) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp).padding(end = 8.dp))
                    Text(stringResource(R.string.tidal_installing))
                }
                LaunchedEffect(Unit) {
                    while (true) { delay(4_000); reload(); if (tidal?.pluginState == "enabled") break }
                }
            } else {
                Button(
                    enabled = !busy,
                    onClick = { scope.launch { busy = true; session.tidalInstall(); reload(); busy = false } },
                ) { Text(stringResource(R.string.tidal_install)) }
            }
            if (t.installError.isNotBlank()) {
                Text(stringResource(R.string.tidal_install_error),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 8.dp))
            }
            return@SectionCard
        }

        if (t.accounts.isEmpty()) {
            Text(stringResource(R.string.tidal_no_accounts),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            t.accounts.forEach { a ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(a.name.ifBlank { a.id }, Modifier.weight(1f))
                    TextButton(onClick = { scope.launch { session.tidalForget(a.id); reload() } }) {
                        Text(stringResource(R.string.tidal_forget))
                    }
                }
            }
        }

        if (authCode != null) {
            Text(stringResource(R.string.tidal_code, authCode!!),
                style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
            OutlinedButton(onClick = { authLink?.let { openUrl(context, it) } }, modifier = Modifier.padding(top = 4.dp)) {
                Text(stringResource(R.string.tidal_open_link))
            }
            if (awaiting) {
                Text(stringResource(R.string.tidal_await),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp))
            }
        } else {
            Button(
                enabled = !busy,
                modifier = Modifier.padding(top = 8.dp),
                onClick = {
                    scope.launch {
                        busy = true
                        val start = session.tidalAuthStart()
                        busy = false
                        if (start != null && start.ok && start.code.isNotBlank()) {
                            authCode = start.code
                            authLink = start.link
                            if (start.link.isNotBlank()) openUrl(context, start.link)
                            awaiting = true
                            val code = start.code
                            repeat(100) {
                                delay(3_000)
                                if (session.tidalAuthStatus(code)?.done == true) {
                                    awaiting = false; authCode = null; authLink = null; reload()
                                    return@launch
                                }
                            }
                            awaiting = false
                        }
                    }
                },
            ) { Text(stringResource(R.string.tidal_connect)) }
        }

        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.tidal_show), Modifier.weight(1f))
            Switch(checked = t.show, onCheckedChange = { on -> scope.launch { session.tidalShow(on); reload() } })
        }
    }
}

@Composable
private fun AudioCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var audio by remember { mutableStateOf<AudioState?>(null) }
    var busy by remember { mutableStateOf(false) }
    suspend fun reload() { audio = session.fetchAudio() }
    LaunchedEffect(session) { reload() }

    SectionCard(Icons.Filled.Speaker, stringResource(R.string.audio_head)) {
        val out = audio?.output ?: ""
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutputButton(stringResource(R.string.audio_dac), out == "dac", busy) {
                scope.launch { busy = true; session.setAudio("dac"); reload(); busy = false }
            }
            OutputButton(stringResource(R.string.audio_hdmi), out == "hdmi", busy) {
                scope.launch { busy = true; session.setAudio("hdmi"); reload(); busy = false }
            }
        }
        if (audio?.rebootRequired == true) {
            Text(
                stringResource(R.string.audio_reboot_required),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        OutlinedButton(
            onClick = { scope.launch { session.testAudio() } },
            modifier = Modifier.padding(top = 8.dp),
        ) {
            Icon(Icons.Filled.NotificationsActive, null, Modifier.padding(end = 8.dp).size(18.dp))
            Text(stringResource(R.string.audio_test))
        }
    }
}

@Composable
private fun OutputButton(label: String, selected: Boolean, busy: Boolean, onClick: () -> Unit) {
    if (selected) {
        Button(onClick = onClick, enabled = !busy) { Text(label) }
    } else {
        OutlinedButton(onClick = onClick, enabled = !busy) { Text(label) }
    }
}

@Composable
private fun VolumeCard(session: PanelSession) {
    val volumes by session.volumes.collectAsStateWithLifecycle()
    SectionCard(Icons.Filled.VolumeUp, stringResource(R.string.volume_label)) {
        val order = listOf("lms" to "LMS", "airplay" to "AirPlay", "bt" to "Bluetooth")
        val shown = order.filter { volumes.containsKey(it.first) }
        if (shown.isEmpty()) {
            Text(stringResource(R.string.now_nothing), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            shown.forEach { (id, label) ->
                VolumeRow(label, volumes[id] ?: 0) { session.setVolume(id, it) }
            }
        }
    }
}

@Composable
private fun VolumeRow(label: String, value: Int, onSet: (Int) -> Unit) {
    var dragging by remember { mutableStateOf(false) }
    var local by remember { mutableStateOf(value.toFloat()) }
    LaunchedEffect(value, dragging) { if (!dragging) local = value.toFloat() }
    Column(Modifier.padding(vertical = 4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium)
        Row(verticalAlignment = Alignment.CenterVertically) {
            androidx.compose.material3.Slider(
                value = local,
                onValueChange = { dragging = true; local = it },
                onValueChangeFinished = { dragging = false; onSet(local.toInt()) },
                valueRange = 0f..100f,
                modifier = Modifier.weight(1f),
            )
            Text("${local.toInt()}%", style = MaterialTheme.typography.labelMedium,
                modifier = Modifier.padding(start = 8.dp))
        }
    }
}

@Composable
private fun AboutCard(session: PanelSession) {
    SectionCard(Icons.Filled.Info, "Synchrofazotron") {
        Text("app ${AppUpdater.currentSha}", style = MaterialTheme.typography.bodyMedium)
        Text(
            "github.com/kwiato/synchrofazotron",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(top = 8.dp),
        )
        Text(
            "cava · glslViewer · Lyrion Music Server · Material Skin · squeezelite · " +
                "Shairport Sync · BlueALSA · DietPi · Tailscale",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 12.dp),
        )
    }
}

@Composable
private fun DeviceCard(session: PanelSession, onChangeDevice: () -> Unit) {
    val scope = rememberCoroutineScope()
    val status by session.status.collectAsStateWithLifecycle()
    var name by remember { mutableStateOf("") }
    var prefilled by remember { mutableStateOf(false) }
    var confirmReboot by remember { mutableStateOf(false) }
    LaunchedEffect(status?.deviceName) {
        val dn = status?.deviceName.orEmpty()
        if (!prefilled && dn.isNotBlank()) { name = dn; prefilled = true }
    }

    SectionCard(Icons.Filled.Tune, stringResource(R.string.device_head)) {
        OutlinedTextField(
            value = name, onValueChange = { name = it }, singleLine = true,
            label = { Text(stringResource(R.string.device_name_label)) },
            modifier = Modifier.fillMaxWidth(),
        )
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = name.isNotBlank(),
                onClick = { scope.launch { session.setName(name.trim()) } },
            ) { Text(stringResource(R.string.device_rename)) }
            OutlinedButton(onClick = { confirmReboot = true }) {
                Icon(Icons.Filled.RestartAlt, null, Modifier.padding(end = 8.dp).size(18.dp))
                Text(stringResource(R.string.device_reboot))
            }
        }
        TextButton(onClick = onChangeDevice, modifier = Modifier.padding(top = 4.dp)) {
            Text(stringResource(R.string.now_change_device))
        }
    }

    if (confirmReboot) {
        ConfirmDialog(
            title = stringResource(R.string.device_reboot_title),
            text = stringResource(R.string.device_reboot_confirm),
            onConfirm = { confirmReboot = false; scope.launch { session.reboot() } },
            onDismiss = { confirmReboot = false },
        )
    }
}

@Composable
private fun TailscaleCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var ts by remember { mutableStateOf<TailscaleState?>(null) }
    var busy by remember { mutableStateOf(false) }
    suspend fun reload() { ts = session.fetchTailscale() }
    LaunchedEffect(session) { reload() }

    SectionCard(Icons.Filled.Link, stringResource(R.string.tailscale_head)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                val ip = ts?.ip.orEmpty()
                if (ip.isNotBlank()) {
                    Text(stringResource(R.string.tailscale_ip, ip), style = MaterialTheme.typography.bodyMedium)
                }
            }
            Switch(
                checked = ts?.active == true,
                enabled = !busy && ts?.installed == true,
                onCheckedChange = { on ->
                    scope.launch { busy = true; session.setTailscale(on); reload(); busy = false }
                },
            )
        }
    }
}

@Composable
private fun UpdateCard(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var checking by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<String?>(null) }
    var confirmUpdate by remember { mutableStateOf(false) }
    var running by remember { mutableStateOf(false) }

    SectionCard(Icons.Filled.SystemUpdate, stringResource(R.string.update_head)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                enabled = !checking,
                onClick = {
                    scope.launch {
                        checking = true
                        val c = session.updateCheck()
                        result = when {
                            c == null || !c.ok -> "fail"
                            c.updateAvailable -> "avail"
                            else -> "current"
                        }
                        checking = false
                    }
                },
            ) {
                if (checking) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.padding(end = 8.dp).size(16.dp))
                }
                Text(stringResource(R.string.update_check))
            }
            Button(onClick = { confirmUpdate = true }, enabled = !running) {
                Icon(Icons.Filled.Download, null, Modifier.padding(end = 8.dp).size(18.dp))
                Text(stringResource(R.string.update_run))
            }
        }
        val msg = when (result) {
            "avail" -> stringResource(R.string.update_available)
            "current" -> stringResource(R.string.update_current)
            "fail" -> stringResource(R.string.update_checkfail)
            else -> null
        }
        if (running) {
            Text(stringResource(R.string.update_running), style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp))
        } else if (msg != null) {
            Text(msg, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
        }
    }

    if (confirmUpdate) {
        ConfirmDialog(
            title = stringResource(R.string.update_title),
            text = stringResource(R.string.update_confirm),
            onConfirm = {
                confirmUpdate = false
                running = true
                scope.launch { session.updateRun() }
            },
            onDismiss = { confirmUpdate = false },
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VizCard(session: PanelSession, onOpenStudio: () -> Unit) {
    val scope = rememberCoroutineScope()
    var viz by remember { mutableStateOf<VizState?>(null) }
    suspend fun reload() { viz = session.fetchViz() }
    LaunchedEffect(session) { reload() }

    SectionCard(Icons.Filled.GraphicEq, stringResource(R.string.viz_head)) {
        val v = viz
        if (v == null || !v.installed) {
            Text(
                stringResource(R.string.viz_not_installed),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@SectionCard
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.viz_enable), Modifier.weight(1f))
            Switch(
                checked = v.active,
                onCheckedChange = { scope.launch { session.vizToggle(); reload() } },
            )
        }
        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutputButton(stringResource(R.string.viz_engine_cava), v.engine == "cava", false) {
                scope.launch { session.vizEngine("cava"); reload() }
            }
            OutputButton(stringResource(R.string.viz_engine_glsl), v.engine == "glsl", !v.glslAvailable) {
                scope.launch { session.vizEngine("glsl", v.shader.ifBlank { v.shaders.firstOrNull()?.id ?: "" }); reload() }
            }
        }
        if (v.engine == "cava") {
            ChipRow(stringResource(R.string.viz_preset), v.presets.map { it.id to it.label }, v.preset) {
                scope.launch { session.vizPreset(it); reload() }
            }
        } else {
            ChipRow(stringResource(R.string.viz_shader), v.shaders.map { it.id to it.label }, v.shader) {
                scope.launch { session.vizEngine("glsl", it); reload() }
            }
        }
        if (v.scales.isNotEmpty()) {
            ChipRow(stringResource(R.string.viz_scale), v.scales.map { it to it }, v.scale) {
                scope.launch { session.vizScale(it); reload() }
            }
        }
        OutlinedButton(onClick = onOpenStudio, modifier = Modifier.padding(top = 8.dp)) {
            Icon(Icons.Filled.Tune, contentDescription = null, modifier = Modifier.padding(end = 8.dp).size(18.dp))
            Text(stringResource(R.string.viz_studio))
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChipRow(label: String, options: List<Pair<String, String>>, selected: String, onPick: (String) -> Unit) {
    Text(label, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 12.dp, bottom = 4.dp))
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (id, lbl) ->
            FilterChip(selected = id == selected, onClick = { onPick(id) }, label = { Text(lbl) })
        }
    }
}

@Composable
private fun AppUpdateCard() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var checking by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) } // avail|current|fail|perm
    var progress by remember { mutableStateOf<Int?>(null) }

    SectionCard(Icons.Filled.Android, stringResource(R.string.app_head)) {
        Text(
            stringResource(R.string.app_version, AppUpdater.currentSha),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                enabled = !checking && progress == null,
                onClick = {
                    scope.launch {
                        checking = true
                        status = when (AppUpdater.updateAvailable()) {
                            true -> "avail"; false -> "current"; null -> "fail"
                        }
                        checking = false
                    }
                },
            ) {
                if (checking) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.padding(end = 8.dp).size(16.dp))
                }
                Text(stringResource(R.string.app_check))
            }
            if (status == "avail" || status == "perm") {
                Button(
                    enabled = progress == null,
                    onClick = {
                        scope.launch {
                            if (!AppUpdater.canInstall(context)) {
                                AppUpdater.openInstallSettings(context)
                                status = "perm"
                                return@launch
                            }
                            progress = 0
                            val file = AppUpdater.download(context) { progress = it }
                            progress = null
                            if (file != null) AppUpdater.install(context, file) else status = "fail"
                        }
                    },
                ) {
                    Icon(Icons.Filled.Download, null, Modifier.padding(end = 8.dp).size(18.dp))
                    Text(stringResource(R.string.app_download_install))
                }
            }
        }
        val p = progress
        if (p != null) {
            Text(stringResource(R.string.app_downloading, p), style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp))
            LinearProgressIndicator(progress = { p / 100f }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
        } else {
            val msg = when (status) {
                "avail" -> stringResource(R.string.app_update_available)
                "current" -> stringResource(R.string.app_up_to_date)
                "fail" -> stringResource(R.string.app_check_fail)
                "perm" -> stringResource(R.string.app_allow_install)
                else -> null
            }
            if (msg != null) Text(msg, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
        }
    }
}

@Composable
private fun ConfirmDialog(title: String, text: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = { TextButton(onClick = onConfirm) { Text(stringResource(R.string.common_confirm)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.common_cancel)) } },
    )
}
