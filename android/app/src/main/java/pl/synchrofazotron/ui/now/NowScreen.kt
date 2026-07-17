package pl.synchrofazotron.ui.now

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import pl.synchrofazotron.R
import pl.synchrofazotron.core.net.PanelClient
import pl.synchrofazotron.core.net.Source
import pl.synchrofazotron.core.net.StatusResponse

@Composable
fun NowScreen(baseUrl: String, onChangeDevice: () -> Unit) {
    val client = remember(baseUrl) { PanelClient(baseUrl) }
    DisposableEffect(client) { onDispose { client.close() } }

    var status by remember { mutableStateOf<StatusResponse?>(null) }
    var reconnecting by remember { mutableStateOf(false) }

    LaunchedEffect(baseUrl) {
        while (true) {
            val next = withContext(Dispatchers.IO) { runCatching { client.status() }.getOrNull() }
            if (next != null) {
                status = next
                reconnecting = false
            } else {
                reconnecting = status != null // keep last data, just flag it
            }
            delay(3_000)
        }
    }

    Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(pad)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.now_device),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = status?.deviceName?.ifBlank { baseUrl } ?: baseUrl,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                TextButton(onClick = onChangeDevice) {
                    Text(stringResource(R.string.now_change_device))
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

            val playing = status?.sources?.filter { it.playing } ?: emptyList()

            if ((status?.playingCount ?: 0) >= 2) {
                Text(
                    text = stringResource(R.string.now_multi_warning),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }

            if (playing.isEmpty()) {
                Text(
                    text = stringResource(R.string.now_nothing),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            } else {
                Card(modifier = Modifier.fillMaxWidth()) {
                    playing.forEachIndexed { i, s ->
                        if (i > 0) HorizontalDivider()
                        SourceRow(s)
                    }
                }
            }
        }
    }
}

@Composable
private fun SourceRow(source: Source) {
    Column(modifier = Modifier.padding(16.dp)) {
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
}
