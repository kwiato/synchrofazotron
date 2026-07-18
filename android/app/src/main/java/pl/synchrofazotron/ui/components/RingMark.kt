package pl.synchrofazotron.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

// The accent used by the ring shimmer — cyan/magenta, kept in every theme just
// like the web app's ConsoleLogo (which flickers the accent even in mono).
private val ShimmerCyan = Color(0xFF2DD4EE)
private val ShimmerMagenta = Color(0xFFC26BF5)

/**
 * The Synchrophasotron monitoring ring — two concentric rows of radial segments
 * in four arcs, with a slow shimmer sweep that lights segments in the accent as
 * it rotates. Evokes the web app's ConsoleLogo.
 */
@Composable
fun RingMark(modifier: Modifier = Modifier, size: Dp = 28.dp, color: Color = LocalContentColor.current) {
    val transition = rememberInfiniteTransition(label = "ring")
    val sweep by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(6000, easing = LinearEasing)),
        label = "sweep",
    )
    val hue by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(9000, easing = LinearEasing), RepeatMode.Reverse),
        label = "hue",
    )
    val accent = lerp(ShimmerCyan, ShimmerMagenta, hue)

    Canvas(modifier = modifier.size(size)) {
        val c = Offset(this.size.width / 2f, this.size.height / 2f)
        val stroke = this.size.minDimension * 0.06f
        val rings = listOf(this.size.minDimension * 0.30f, this.size.minDimension * 0.44f)
        val perArc = 5
        for (r in rings) {
            for (arc in 0 until 4) {
                val base = arc * 90.0 + 8.0
                for (k in 0 until perArc) {
                    val deg = base + k * (74.0 / (perArc - 1))
                    val ang = Math.toRadians(deg)
                    val inner = r - stroke
                    val outer = r + stroke
                    val p1 = Offset(c.x + (cos(ang) * inner).toFloat(), c.y + (sin(ang) * inner).toFloat())
                    val p2 = Offset(c.x + (cos(ang) * outer).toFloat(), c.y + (sin(ang) * outer).toFloat())
                    // angular distance to the sweep -> hotness
                    val diff = abs(deg - sweep) % 360.0
                    val dist = minOf(diff, 360.0 - diff)
                    val hot = (1f - (dist / 45.0).toFloat()).coerceIn(0f, 1f)
                    val segColor = lerp(color, accent, hot * 0.9f)
                    drawLine(color = segColor, start = p1, end = p2, strokeWidth = stroke, cap = StrokeCap.Round)
                }
            }
        }
    }
}
