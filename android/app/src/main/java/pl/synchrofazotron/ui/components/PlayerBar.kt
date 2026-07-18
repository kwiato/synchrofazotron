package pl.synchrofazotron.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import kotlinx.coroutines.launch
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.Source
import pl.synchrofazotron.core.net.StatusResponse

@Composable
fun PlayerBar(session: PanelSession, onHome: () -> Unit, modifier: Modifier = Modifier) {
    val status by session.status.collectAsStateWithLifecycle()
    val volumes by session.volumes.collectAsStateWithLifecycle()

    val p = primarySource(status)
    val ctrlOff = !(p?.controllable == true && p.id.isNotBlank())

    // Drag-follow sheet: progress 0(closed)..1(open) tracks the finger, snaps on release.
    val progress = remember { Animatable(0f) }
    val scope = rememberCoroutineScope()
    var contentH by remember { mutableIntStateOf(0) }
    val density = LocalDensity.current
    val fallbackPx = with(density) { 280.dp.toPx() }
    fun dragSpan() = if (contentH > 0) contentH.toFloat() else fallbackPx
    fun settle() { scope.launch { progress.animateTo(if (progress.value > 0.4f) 1f else 0f) } }
    val open = progress.value > 0.5f

    Surface(
        color = MaterialTheme.colorScheme.inverseSurface,
        contentColor = MaterialTheme.colorScheme.inverseOnSurface,
        shape = MaterialTheme.shapes.large,
        tonalElevation = 6.dp,
        shadowElevation = 8.dp,
        modifier = modifier.fillMaxWidth(),
    ) {
        Column {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(with(density) { (contentH * progress.value).toDp() })
                    .clipToBounds(),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .wrapContentHeight(align = Alignment.Top, unbounded = true)
                        .onSizeChanged { contentH = it.height },
                ) {
                    SourcesSheet(status = status, volumes = volumes, session = session)
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .pointerInput(Unit) {
                        detectVerticalDragGestures(
                            onDragEnd = { settle() },
                            onDragCancel = { settle() },
                        ) { change, dy ->
                            change.consume()
                            scope.launch { progress.snapTo((progress.value - dy / dragSpan()).coerceIn(0f, 1f)) }
                        }
                    }
                    .padding(horizontal = 8.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = { scope.launch { progress.animateTo(if (open) 0f else 1f) } }) {
                    Icon(
                        if (open) Icons.Filled.KeyboardArrowDown else Icons.Filled.KeyboardArrowUp,
                        contentDescription = stringResource(R.string.sheet_sources),
                    )
                }
                Eq(on = p?.playing == true, modifier = Modifier.padding(horizontal = 4.dp))
                Column(
                    modifier = Modifier.weight(1f).padding(horizontal = 8.dp).clickable(onClick = onHome),
                ) {
                    Text(
                        text = p?.let { it.detail.ifBlank { it.name } } ?: stringResource(R.string.now_nothing),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (p != null) {
                        Text(
                            text = srcSub(p),
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                IconButton(enabled = !ctrlOff, onClick = { p?.let { session.control(it.id, "prev") } }) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, "prev")
                }
                FilledIconButton(
                    enabled = !ctrlOff,
                    onClick = { p?.let { session.control(it.id, "toggle") } },
                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.inverseOnSurface,
                        contentColor = MaterialTheme.colorScheme.inverseSurface,
                    ),
                ) {
                    Icon(
                        if (p?.playing == true) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = null,
                    )
                }
                IconButton(enabled = !ctrlOff, onClick = { p?.let { session.control(it.id, "next") } }) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "next")
                }
            }
        }
    }
}

@Composable
private fun SourcesSheet(status: StatusResponse?, volumes: Map<String, Int>, session: PanelSession) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        // Wi-Fi + BT glance
        val ssid = status?.wifiSsid.orEmpty()
        val secs = status?.pairSecondsLeft ?: 0
        val btConn = status?.connected.orEmpty()
        val btText = when {
            secs > 0 -> stringResource(R.string.glance_bt_pairing, secs)
            btConn.isNotEmpty() -> btConn.joinToString { it.name }
            status?.btPowered == true -> stringResource(R.string.glance_bt_ready)
            else -> stringResource(R.string.glance_bt_off)
        }
        val btDot = when {
            secs > 0 -> StatusWarn
            btConn.isNotEmpty() -> StatusGood
            status?.btPowered == true -> StatusNeutral
            else -> StatusDanger
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            GlanceItem(
                icon = Icons.Filled.Wifi,
                dot = if (ssid.isNotBlank()) StatusGood else StatusDanger,
                text = ssid.ifBlank { stringResource(R.string.glance_wifi_off) },
                modifier = Modifier.weight(1f),
            )
            GlanceItem(
                icon = Icons.Filled.Bluetooth,
                dot = btDot,
                text = btText,
                modifier = Modifier.weight(1f),
            )
        }

        Text(
            stringResource(R.string.sheet_sources),
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
        )
        val sources = status?.sources.orEmpty()
        if (sources.isEmpty()) {
            Text(stringResource(R.string.now_nothing), style = MaterialTheme.typography.bodySmall)
        } else {
            sources.forEach { s -> SheetRow(s) { if (s.controllable && s.id.isNotBlank()) session.control(s.id, "toggle") } }
        }

        // primary volume
        val p = primarySource(status)
        if (p != null && volumes.containsKey(p.id)) {
            val v = volumes[p.id] ?: 0
            var dragging by remember { mutableStateOf(false) }
            var local by remember { mutableFloatStateOf(v.toFloat()) }
            if (!dragging) local = v.toFloat()
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("${local.toInt()}%", style = MaterialTheme.typography.labelSmall, modifier = Modifier.size(width = 40.dp, height = 20.dp))
                Slider(
                    value = local,
                    onValueChange = { dragging = true; local = it },
                    onValueChangeFinished = { dragging = false; session.setVolume(p.id, local.toInt()) },
                    valueRange = 0f..100f,
                    colors = SliderDefaults.colors(
                        thumbColor = LocalContentColor.current,
                        activeTrackColor = LocalContentColor.current,
                        inactiveTrackColor = LocalContentColor.current.copy(alpha = 0.3f),
                    ),
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun SheetRow(source: Source, onToggle: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Eq(on = source.playing)
        Column(Modifier.weight(1f).padding(start = 8.dp)) {
            Text("${source.name} — ${source.state}", style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (source.detail.isNotBlank()) {
                Text(source.detail, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        if (source.controllable && source.id.isNotBlank()) {
            IconButton(onClick = onToggle) {
                Icon(if (source.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow, contentDescription = null)
            }
        }
    }
}

// Status colors — identical across themes, like the web app's dots.
private val StatusGood = Color(0xFF34D399)
private val StatusWarn = Color(0xFFFBBF24)
private val StatusDanger = Color(0xFFF87171)
private val StatusNeutral = Color(0xFF9AA1AB)

@Composable
private fun GlanceItem(icon: ImageVector, dot: Color, text: String, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp))
        Box(
            Modifier.padding(horizontal = 5.dp).size(7.dp).clip(CircleShape).background(dot),
        )
        Text(text, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
