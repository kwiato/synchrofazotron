package pl.synchrofazotron.ui.settings

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
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.GraphicEq
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.AudioState
import pl.synchrofazotron.core.net.BtDevice
import pl.synchrofazotron.core.net.BtInfo
import pl.synchrofazotron.core.net.TailscaleState
import pl.synchrofazotron.core.net.VizState
import pl.synchrofazotron.core.net.WifiInfo
import pl.synchrofazotron.core.net.WifiNetwork

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(session: PanelSession, onBack: () -> Unit, onOpenStudio: () -> Unit) {
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
            WifiCard(session)
            BluetoothCard(session)
            AudioCard(session)
            VizCard(session, onOpenStudio)
            DeviceCard(session)
            TailscaleCard(session)
            UpdateCard(session)
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
private fun DeviceCard(session: PanelSession) {
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
private fun ConfirmDialog(title: String, text: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = { TextButton(onClick = onConfirm) { Text(stringResource(R.string.common_confirm)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.common_cancel)) } },
    )
}
