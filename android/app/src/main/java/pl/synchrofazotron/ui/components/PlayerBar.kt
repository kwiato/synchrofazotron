package pl.synchrofazotron.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.em
import pl.synchrofazotron.ui.theme.Spacing
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
    var netDrag by remember { mutableFloatStateOf(0f) } // per-gesture: <0 up (open), >0 down (close)
    val density = LocalDensity.current
    val fallbackPx = with(density) { 280.dp.toPx() }
    fun dragSpan() = if (contentH > 0) contentH.toFloat() else fallbackPx
    // Settle by drag direction so a downward drag always collapses (not just when
    // it crosses a fixed fraction); a near-zero net drag snaps to the nearest end.
    fun settle() {
        val target = when {
            netDrag < 0f -> 1f
            netDrag > 0f -> 0f
            else -> if (progress.value > 0.5f) 1f else 0f
        }
        scope.launch { progress.animateTo(target) }
    }
    val open = progress.value > 0.5f

    Surface(
        color = MaterialTheme.colorScheme.inverseSurface,
        contentColor = MaterialTheme.colorScheme.inverseOnSurface,
        shape = RoundedCornerShape(18.dp),
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
                            onDragStart = { netDrag = 0f },
                            onDragEnd = { settle() },
                            onDragCancel = { settle() },
                        ) { change, dy ->
                            change.consume()
                            netDrag += dy
                            scope.launch { progress.snapTo((progress.value - dy / dragSpan()).coerceIn(0f, 1f)) }
                        }
                    }
                    .padding(horizontal = Spacing.xs, vertical = Spacing.xs2),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs3),
            ) {
                IconButton(onClick = { scope.launch { progress.animateTo(if (open) 0f else 1f) } }) {
                    Icon(
                        if (open) Icons.Filled.KeyboardArrowDown else Icons.Filled.KeyboardArrowUp,
                        contentDescription = stringResource(R.string.sheet_sources),
                    )
                }
                Eq(on = p?.playing == true)
                Column(
                    modifier = Modifier.weight(1f).padding(horizontal = Spacing.xs3).clickable(onClick = onHome),
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
                    modifier = Modifier.size(52.dp),
                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.inverseOnSurface,
                        contentColor = MaterialTheme.colorScheme.inverseSurface,
                    ),
                ) {
                    Icon(
                        if (p?.playing == true) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(26.dp),
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
            stringResource(R.string.sheet_sources).uppercase(),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.08.em,
            color = LocalContentColor.current.copy(alpha = 0.6f),
            modifier = Modifier.padding(top = Spacing.xs, bottom = Spacing.xs3),
        )
        val sources = status?.sources.orEmpty()
        val p = primarySource(status)
        if (sources.isEmpty()) {
            Text(stringResource(R.string.now_nothing), style = MaterialTheme.typography.bodySmall)
        } else {
            // Non-followed sources sit as plain rows; the followed one is boxed below.
            sources.filter { it.id != p?.id }.forEach { s ->
                SheetRow(s) { if (s.controllable && s.id.isNotBlank()) session.control(s.id, "toggle") }
            }
            if (p != null) {
                DacOwnerBox(state = p.state) {
                    SheetRow(p, emphasized = true) { if (p.controllable && p.id.isNotBlank()) session.control(p.id, "toggle") }
                    if (volumes.containsKey(p.id)) {
                        VolumeRow(sourceId = p.id, value = volumes[p.id] ?: 0, session = session)
                    }
                }
            }
        }
    }
}

/**
 * The followed source's row + volume inside a subtle outline, with its output
 * state sitting on the top border (fieldset-legend style, the web `.dac-owner`).
 */
@Composable
private fun DacOwnerBox(state: String, content: @Composable ColumnScope.() -> Unit) {
    val line = LocalContentColor.current.copy(alpha = 0.28f)
    Box(Modifier.padding(top = Spacing.xs)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, line, RoundedCornerShape(12.dp))
                .padding(horizontal = Spacing.xs2, vertical = Spacing.xs3),
            content = content,
        )
        Text(
            text = state,
            style = MaterialTheme.typography.labelSmall,
            color = LocalContentColor.current.copy(alpha = 0.6f),
            modifier = Modifier
                .align(Alignment.TopEnd)
                .offset(x = (-12).dp, y = (-7).dp)
                .background(MaterialTheme.colorScheme.inverseSurface)
                .padding(horizontal = 4.dp),
        )
    }
}

@Composable
private fun VolumeRow(sourceId: String, value: Int, session: PanelSession) {
    var dragging by remember { mutableStateOf(false) }
    var local by remember { mutableFloatStateOf(value.toFloat()) }
    if (!dragging) local = value.toFloat()
    Row(Modifier.fillMaxWidth().padding(top = Spacing.xs3), verticalAlignment = Alignment.CenterVertically) {
        Text("${local.toInt()}%", style = MaterialTheme.typography.labelSmall, modifier = Modifier.size(width = 40.dp, height = 20.dp))
        Slider(
            value = local,
            onValueChange = { dragging = true; local = it },
            onValueChangeFinished = { dragging = false; session.setVolume(sourceId, local.toInt()) },
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

@Composable
private fun SheetRow(source: Source, emphasized: Boolean = false, onToggle: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = Spacing.xs3), verticalAlignment = Alignment.CenterVertically) {
        Eq(on = source.playing)
        Column(Modifier.weight(1f).padding(start = Spacing.xs2)) {
            Text("${source.name} — ${source.state}", style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (source.detail.isNotBlank()) {
                Text(source.detail, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        if (source.controllable && source.id.isNotBlank()) {
            val icon = if (source.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow
            if (emphasized) {
                // The followed source gets a solid white square button, like the web app.
                FilledIconButton(
                    onClick = onToggle,
                    shape = RoundedCornerShape(12.dp),
                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.inverseOnSurface,
                        contentColor = MaterialTheme.colorScheme.inverseSurface,
                    ),
                ) { Icon(icon, contentDescription = null) }
            } else {
                IconButton(onClick = onToggle) { Icon(icon, contentDescription = null) }
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
