package pl.synchrofazotron.ui.now

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import pl.synchrofazotron.core.net.Source

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NowScreen(session: PanelSession, onChangeDevice: () -> Unit, onOpenSettings: () -> Unit) {
    val status by session.status.collectAsStateWithLifecycle()
    val reconnecting by session.reconnecting.collectAsStateWithLifecycle()
    val volumes by session.volumes.collectAsStateWithLifecycle()
    val hud by session.volumeHud.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var refreshing by remember { mutableStateOf(false) }

    Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
        Box(modifier = Modifier.fillMaxSize().padding(pad)) {
            PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = {
                    scope.launch { refreshing = true; session.refreshNow(); refreshing = false }
                },
                modifier = Modifier.fillMaxSize(),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 20.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = stringResource(R.string.now_device),
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                text = status?.deviceName?.ifBlank { session.baseUrl } ?: session.baseUrl,
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                        TextButton(onClick = onChangeDevice) {
                            Text(stringResource(R.string.now_change_device))
                        }
                        IconButton(onClick = onOpenSettings) {
                            Icon(Icons.Filled.Settings, stringResource(R.string.settings_title))
                        }
                    }

                    AnimatedVisibility(visible = reconnecting) {
                        Text(
                            text = stringResource(R.string.now_reconnecting),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }

                    Text(
                        text = stringResource(R.string.now_title),
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(top = 24.dp, bottom = 8.dp),
                    )

                    if ((status?.playingCount ?: 0) >= 2) {
                        Text(
                            text = stringResource(R.string.now_multi_warning),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                    }

                    val sources = status?.sources ?: emptyList()
                    val shown = sources.filter { it.playing || it.controllable }

                    if (shown.isEmpty()) {
                        Text(
                            text = stringResource(R.string.now_nothing),
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 8.dp),
                        )
                    } else {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            shown.forEachIndexed { i, s ->
                                if (i > 0) HorizontalDivider()
                                SourceRow(
                                    source = s,
                                    volume = volumes[s.id],
                                    onToggle = { session.control(s.id, "toggle") },
                                    onVolume = { session.setVolume(s.id, it) },
                                )
                            }
                        }
                    }
                    Column(Modifier.padding(bottom = 24.dp)) {}
                }
            }

            VolumeHud(
                value = hud,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 12.dp),
            )
        }
    }
}

@Composable
private fun SourceRow(source: Source, volume: Int?, onToggle: () -> Unit, onVolume: (Int) -> Unit) {
    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = source.name, style = MaterialTheme.typography.titleSmall)
                val detail = source.detail.ifBlank {
                    stringResource(if (source.playing) R.string.state_playing else R.string.state_idle)
                }
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (source.controllable) {
                FilledIconButton(onClick = onToggle) {
                    Icon(
                        imageVector = if (source.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = stringResource(
                            if (source.playing) R.string.action_pause else R.string.action_play,
                        ),
                    )
                }
            }
        }
        if (volume != null) {
            var dragging by remember { mutableStateOf(false) }
            var local by remember { mutableStateOf(volume.toFloat()) }
            // Track the polled value while not dragging; drag stays smooth and
            // only posts once, on release.
            LaunchedEffect(volume, dragging) { if (!dragging) local = volume.toFloat() }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                Icon(
                    Icons.Filled.VolumeUp,
                    contentDescription = stringResource(R.string.volume_label),
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Slider(
                    value = local,
                    onValueChange = { dragging = true; local = it },
                    onValueChangeFinished = { dragging = false; onVolume(local.toInt()) },
                    valueRange = 0f..100f,
                    modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                )
                Text(
                    text = "${local.toInt()}%",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun VolumeHud(value: Int?, modifier: Modifier = Modifier) {
    AnimatedVisibility(visible = value != null, enter = fadeIn(), exit = fadeOut(), modifier = modifier) {
        Surface(
            color = MaterialTheme.colorScheme.inverseSurface,
            contentColor = MaterialTheme.colorScheme.inverseOnSurface,
            shape = MaterialTheme.shapes.large,
            tonalElevation = 4.dp,
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = Icons.Filled.VolumeUp,
                    contentDescription = stringResource(R.string.volume_label),
                    modifier = Modifier.size(20.dp),
                )
                LinearProgressIndicator(
                    progress = { (value ?: 0) / 100f },
                    modifier = Modifier.padding(start = 12.dp).size(width = 120.dp, height = 4.dp),
                )
                Text(
                    text = "${value ?: 0}%",
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.padding(start = 12.dp),
                )
            }
        }
    }
}
