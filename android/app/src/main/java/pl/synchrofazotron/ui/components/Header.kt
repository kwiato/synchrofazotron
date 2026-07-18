package pl.synchrofazotron.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.ui.theme.Spacing

/** Persistent top chrome: ring mark (tap = Now), BT pair, cog. */
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
        modifier = Modifier.fillMaxWidth().padding(horizontal = Spacing.xs, vertical = Spacing.xs2),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RingMark(
            modifier = Modifier.clip(RoundedCornerShape(12.dp)).clickable(onClick = onHome),
            size = 34.dp,
        )
        Spacer(Modifier.weight(1f))
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
