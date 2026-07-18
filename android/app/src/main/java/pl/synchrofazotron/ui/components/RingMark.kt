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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.abs

// Accent kept in every theme, like the web ConsoleLogo (flickers even in mono).
private val ShimmerCyan = Color(0xFF2DD4EE)
private val ShimmerMagenta = Color(0xFFC26BF5)

// Ported from ConsoleLogo.jsx: four arcs (gaps at 0/90/180/270), 5 rectangular
// segments each, two concentric rows. viewBox 124, W=6 H=10, radii 40/54.
private val ARCS = listOf(45f, 135f, 225f, 315f)
private val OFFS = listOf(-32f, -16f, 0f, 16f, 32f)
private val ROWS = listOf(40f, 54f)

/** The Synchrophasotron monitoring ring — rectangular segments with an accent
 *  shimmer sweeping around it. */
@Composable
fun RingMark(modifier: Modifier = Modifier, size: Dp = 28.dp, color: Color = LocalContentColor.current) {
    val transition = rememberInfiniteTransition(label = "ring")
    val sweep by transition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(5000, easing = LinearEasing)),
        label = "sweep",
    )
    val hue by transition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(8000, easing = LinearEasing), RepeatMode.Reverse),
        label = "hue",
    )
    val accent = lerp(ShimmerCyan, ShimmerMagenta, hue)

    Canvas(modifier = modifier.size(size)) {
        val s = this.size.minDimension / 124f
        val w = 6f * s
        val h = 10f * s
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        for (arc in ARCS) {
            for (off in OFFS) {
                val deg = arc + off
                for (rowR in ROWS) {
                    val r = rowR * s
                    val diff = abs(deg - sweep) % 360.0
                    val dist = minOf(diff, 360.0 - diff)
                    val hot = (1f - (dist / 40.0).toFloat()).coerceIn(0f, 1f)
                    val segColor = lerp(color, accent, hot)
                    rotate(degrees = deg, pivot = Offset(cx, cy)) {
                        drawRoundRect(
                            color = segColor,
                            topLeft = Offset(cx - w / 2f, cy - r - h / 2f),
                            size = Size(w, h),
                            cornerRadius = CornerRadius(w * 0.35f, w * 0.35f),
                        )
                    }
                }
            }
        }
    }
}
