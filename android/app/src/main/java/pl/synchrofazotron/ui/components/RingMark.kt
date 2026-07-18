package pl.synchrofazotron.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.dp
import kotlin.math.cos
import kotlin.math.sin

/**
 * The Synchrophasotron monitoring ring — two concentric rows of radial segments
 * in four arcs. A small, static evocation of the web app's ConsoleLogo mark.
 */
@Composable
fun RingMark(modifier: Modifier = Modifier, color: Color = LocalContentColor.current) {
    Canvas(modifier = modifier.size(28.dp)) {
        val c = Offset(size.width / 2f, size.height / 2f)
        val stroke = size.minDimension * 0.06f
        val rings = listOf(size.minDimension * 0.30f, size.minDimension * 0.44f)
        // four arcs of segments, leaving gaps between arcs
        val perArc = 5
        for (r in rings) {
            for (arc in 0 until 4) {
                val base = arc * 90.0 + 8.0
                for (k in 0 until perArc) {
                    val ang = Math.toRadians(base + k * (74.0 / (perArc - 1)))
                    val inner = r - stroke
                    val outer = r + stroke
                    val p1 = Offset(c.x + (cos(ang) * inner).toFloat(), c.y + (sin(ang) * inner).toFloat())
                    val p2 = Offset(c.x + (cos(ang) * outer).toFloat(), c.y + (sin(ang) * outer).toFloat())
                    drawLine(color = color, start = p1, end = p2, strokeWidth = stroke, cap = StrokeCap.Round)
                }
            }
        }
    }
}
