package pl.synchrofazotron.ui.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.background
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

/** Tiny animated equalizer glyph — the "is playing" indicator. */
@Composable
fun Eq(on: Boolean, modifier: Modifier = Modifier, bars: Int = 3, color: Color = LocalContentColor.current) {
    val transition = rememberInfiniteTransition(label = "eq")
    Row(modifier = modifier.size(width = (bars * 5 - 2).dp, height = 14.dp), verticalAlignment = Alignment.Bottom) {
        repeat(bars) { i ->
            val h by transition.animateFloat(
                initialValue = 0.25f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(durationMillis = 500 + i * 120, easing = androidx.compose.animation.core.LinearEasing),
                    repeatMode = RepeatMode.Reverse,
                ),
                label = "bar$i",
            )
            val frac = if (on) h else 0.2f
            Spacer(
                modifier = Modifier
                    .width(3.dp)
                    .fillMaxHeight(frac)
                    .clip(RoundedCornerShape(1.dp))
                    .background(color),
            )
            if (i < bars - 1) Spacer(Modifier.width(2.dp))
        }
    }
}
