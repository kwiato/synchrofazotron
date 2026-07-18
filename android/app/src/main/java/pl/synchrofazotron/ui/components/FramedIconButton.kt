package pl.synchrofazotron.ui.components

import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedIconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Icon button that always carries a frame: an outlined ring at rest, and — when
 * [active] — a solid negative fill (onSurface background, surface icon), matching
 * the mono theme's "active = full inverse" rule from the web panel.
 */
@Composable
fun FramedIconButton(
    onClick: () -> Unit,
    icon: ImageVector,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    active: Boolean = false,
    enabled: Boolean = true,
) {
    if (active) {
        FilledIconButton(
            onClick = onClick,
            modifier = modifier,
            enabled = enabled,
            colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = MaterialTheme.colorScheme.onSurface,
                contentColor = MaterialTheme.colorScheme.surface,
            ),
        ) { Icon(icon, contentDescription) }
    } else {
        OutlinedIconButton(
            onClick = onClick,
            modifier = modifier,
            enabled = enabled,
        ) { Icon(icon, contentDescription) }
    }
}
