package pl.synchrofazotron.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Monochrome palette — the current Synchrofazotron look (black/white), matching
// the web panel's `system` default (mono-light / mono-dark). The legacy "neon"
// accent (cyan -> magenta) is intentionally NOT the default here.

private val Ink = Color(0xFF0B0B0C)
private val Paper = Color(0xFFFFFFFF)
private val InkMuted = Color(0xFF6B7280)
private val PaperMuted = Color(0xFF9AA1AB)

private val MonoLight = lightColorScheme(
    primary = Ink,
    onPrimary = Paper,
    secondary = Ink,
    onSecondary = Paper,
    background = Paper,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Color(0xFFF1F2F4),
    onSurfaceVariant = InkMuted,
    outline = Color(0xFF1A1B1D),
    error = Color(0xFFB00020),
)

private val MonoDark = darkColorScheme(
    primary = Paper,
    onPrimary = Ink,
    secondary = Paper,
    onSecondary = Ink,
    background = Color(0xFF060708),
    onBackground = Paper,
    surface = Color(0xFF0E0F11),
    onSurface = Paper,
    surfaceVariant = Color(0xFF16181B),
    onSurfaceVariant = PaperMuted,
    outline = Color(0xFFE7E9ED),
    error = Color(0xFFF87171),
)

@Composable
fun SynchrofazotronTheme(
    dark: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (dark) MonoDark else MonoLight,
        typography = Typography(),
        content = content,
    )
}
