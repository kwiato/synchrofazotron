package pl.synchrofazotron.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Transient feedback pill (the web app's Droplet), pinned near the top. Slides
 * and scales in, shows a message, then auto-hides (timing owned by the caller).
 */
@Composable
fun Droplet(text: String?, modifier: Modifier = Modifier) {
    AnimatedVisibility(
        visible = text != null,
        enter = slideInVertically { -it } + fadeIn() + scaleIn(initialScale = 0.85f),
        exit = slideOutVertically { -it } + fadeOut() + scaleOut(targetScale = 0.85f),
        modifier = modifier,
    ) {
        Surface(
            color = MaterialTheme.colorScheme.inverseSurface,
            contentColor = MaterialTheme.colorScheme.inverseOnSurface,
            shape = RoundedCornerShape(999.dp),
            shadowElevation = 8.dp,
        ) {
            Text(
                text = text ?: "",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 11.dp),
            )
        }
    }
}
