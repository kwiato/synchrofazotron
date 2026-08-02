package pl.synchrofazotron.ui.components

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import pl.synchrofazotron.ui.theme.Spacing

/**
 * Segmented pill control matching the web panel's mono tabs: an inverse-surface
 * track (near-black on light, near-white on dark) with the active segment as a
 * surface-coloured thumb that slides between positions. Inactive labels are
 * muted; the active one takes the surface ink. Used for the Now/Radio/Viz tabs,
 * the Settings sections, and the viz engine picker.
 */
@Composable
fun SegTabs(
    items: List<Pair<String, String>>, // (id, label)
    active: String,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    fillWidth: Boolean = true,
) {
    val selected = items.indexOfFirst { it.first == active }.coerceAtLeast(0)
    val pill = RoundedCornerShape(percent = 50)
    Surface(
        color = MaterialTheme.colorScheme.inverseSurface,
        contentColor = MaterialTheme.colorScheme.inverseOnSurface,
        shape = pill,
        modifier = if (fillWidth) modifier.fillMaxWidth() else modifier,
    ) {
        BoxWithConstraints(Modifier.padding(Spacing.xs3).height(38.dp)) {
            val segW = maxWidth / items.size
            val thumbX by animateDpAsState(targetValue = segW * selected, label = "segThumb")
            // Sliding active thumb.
            Box(
                Modifier
                    .padding(start = thumbX)
                    .width(segW)
                    .fillMaxHeight()
                    .shadow(3.dp, pill)
                    .background(MaterialTheme.colorScheme.surface, pill),
            )
            Row(Modifier.fillMaxSize()) {
                items.forEachIndexed { i, (id, label) ->
                    val isSel = i == selected
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(pill)
                            .clickable(
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null,
                            ) { onChange(id) },
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = label,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            textAlign = TextAlign.Center,
                            style = LocalTextStyle.current.copy(
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp,
                            ),
                            color = if (isSel) {
                                MaterialTheme.colorScheme.onSurface
                            } else {
                                MaterialTheme.colorScheme.inverseOnSurface.copy(alpha = 0.60f)
                            },
                            modifier = Modifier.padding(horizontal = 4.dp),
                        )
                    }
                }
            }
        }
    }
}
