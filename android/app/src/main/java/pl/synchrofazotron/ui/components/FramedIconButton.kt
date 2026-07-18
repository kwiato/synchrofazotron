package pl.synchrofazotron.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp

/**
 * Icon button that always carries a frame — a rounded-square (12dp) outline at
 * rest, and a solid negative fill (onSurface background, surface icon) when
 * [active], matching the web panel's `.iconbtn` / `.iconbtn.active` rule. Square
 * corners (not a circle) mirror the original header buttons.
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
    val shape = RoundedCornerShape(12.dp)
    val scheme = MaterialTheme.colorScheme
    val base = Modifier
        .size(40.dp)
        .clip(shape)
        .clickable(
            enabled = enabled,
            interactionSource = remember { MutableInteractionSource() },
            indication = ripple(),
            onClick = onClick,
        )
    Box(
        modifier = modifier
            .then(base)
            .then(
                if (active) Modifier.background(scheme.onSurface, shape)
                else Modifier.border(BorderStroke(1.dp, scheme.outline), shape)
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = if (active) scheme.surface else scheme.onSurface,
            modifier = Modifier.size(20.dp),
        )
    }
}
