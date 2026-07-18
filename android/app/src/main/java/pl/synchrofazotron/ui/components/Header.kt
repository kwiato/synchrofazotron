package pl.synchrofazotron.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession

/** Persistent top chrome: ring mark + device name (tap = Now), BT pair, cog. */
@Composable
fun Header(
    session: PanelSession,
    onHome: () -> Unit,
    onToggleSettings: () -> Unit,
    isSettings: Boolean,
) {
    val status by session.status.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val secs = status?.pairSecondsLeft ?: 0
    val connected = status?.connected.orEmpty()
    val pairActive = secs > 0 || connected.isNotEmpty()

    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier.weight(1f).clickable(onClick = onHome),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RingMark()
            Text(
                text = status?.deviceName?.ifBlank { session.baseUrl } ?: session.baseUrl,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(start = 10.dp),
            )
        }
        if (secs > 0) {
            Text(
                "${secs}s",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(end = 6.dp),
            )
        }
        FramedIconButton(
            onClick = { scope.launch { session.pair() } },
            icon = Icons.Filled.Bluetooth,
            contentDescription = stringResource(R.string.bt_pair),
            active = pairActive,
        )
        FramedIconButton(
            onClick = onToggleSettings,
            icon = Icons.Filled.Settings,
            contentDescription = stringResource(R.string.settings_title),
            active = isSettings,
            modifier = Modifier.padding(start = 6.dp),
        )
    }
}
