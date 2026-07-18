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

// Fully monochrome — every container/accent slot is neutral so nothing renders
// in Material's default purple (segmented selection, chips, filled buttons).
private val MonoLight = lightColorScheme(
    primary = Ink,
    onPrimary = Paper,
    primaryContainer = Color(0xFF1A1B1D),
    onPrimaryContainer = Paper,
    secondary = Ink,
    onSecondary = Paper,
    secondaryContainer = Color(0xFFE7E7EA),
    onSecondaryContainer = Ink,
    tertiary = Ink,
    onTertiary = Paper,
    tertiaryContainer = Color(0xFFE7E7EA),
    onTertiaryContainer = Ink,
    background = Paper,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Color(0xFFF1F2F4),
    onSurfaceVariant = InkMuted,
    surfaceContainerLowest = Paper,
    surfaceContainerLow = Color(0xFFF6F6F8),
    surfaceContainer = Color(0xFFF1F1F4),
    surfaceContainerHigh = Color(0xFFEBEBEE),
    surfaceContainerHighest = Color(0xFFE6E6E9),
    outline = Color(0xFF1A1B1D),
    outlineVariant = Color(0xFFCFCFD3),
    inverseSurface = Ink,
    inverseOnSurface = Paper,
    error = Color(0xFFB00020),
)

private val MonoDark = darkColorScheme(
    primary = Paper,
    onPrimary = Ink,
    primaryContainer = Color(0xFFE7E9ED),
    onPrimaryContainer = Ink,
    secondary = Paper,
    onSecondary = Ink,
    secondaryContainer = Color(0xFF23262B),
    onSecondaryContainer = Paper,
    tertiary = Paper,
    onTertiary = Ink,
    tertiaryContainer = Color(0xFF23262B),
    onTertiaryContainer = Paper,
    background = Color(0xFF060708),
    onBackground = Paper,
    surface = Color(0xFF0E0F11),
    onSurface = Paper,
    surfaceVariant = Color(0xFF16181B),
    onSurfaceVariant = PaperMuted,
    surfaceContainerLowest = Color(0xFF060708),
    surfaceContainerLow = Color(0xFF111316),
    surfaceContainer = Color(0xFF16181B),
    surfaceContainerHigh = Color(0xFF1E2125),
    surfaceContainerHighest = Color(0xFF25282D),
    outline = Color(0xFFE7E9ED),
    outlineVariant = Color(0xFF34373C),
    inverseSurface = Paper,
    inverseOnSurface = Ink,
    error = Color(0xFFF87171),
)

// Legacy "neon" — dark cyberpunk with a cyan -> magenta accent. Opt-in only.
private val NeonScheme = darkColorScheme(
    primary = Color(0xFF2DD4EE),
    onPrimary = Color(0xFF07090E),
    primaryContainer = Color(0xFF163B45),
    onPrimaryContainer = Color(0xFFC8F2FF),
    secondary = Color(0xFFC26BF5),
    onSecondary = Color(0xFF07090E),
    secondaryContainer = Color(0xFF2A1F3A),
    onSecondaryContainer = Color(0xFFE8D8FF),
    tertiary = Color(0xFF7C8CF8),
    background = Color(0xFF07090E),
    onBackground = Color(0xFFE8EEF6),
    surface = Color(0xFF10151D),
    onSurface = Color(0xFFE8EEF6),
    surfaceVariant = Color(0xFF161D28),
    onSurfaceVariant = Color(0xFF8B98A9),
    surfaceContainerLowest = Color(0xFF07090E),
    surfaceContainerLow = Color(0xFF0F141C),
    surfaceContainer = Color(0xFF141A24),
    surfaceContainerHigh = Color(0xFF1A212C),
    surfaceContainerHighest = Color(0xFF232C38),
    outline = Color(0xFF2E3C50),
    outlineVariant = Color(0xFF202A38),
    inverseSurface = Color(0xFFE8EEF6),
    inverseOnSurface = Color(0xFF10151D),
    error = Color(0xFFF87171),
)

@Composable
fun SynchrofazotronTheme(
    pref: String = "system",
    content: @Composable () -> Unit,
) {
    val scheme = when (pref) {
        "mono-light" -> MonoLight
        "mono-dark" -> MonoDark
        "neon" -> NeonScheme
        else -> if (isSystemInDarkTheme()) MonoDark else MonoLight
    }
    MaterialTheme(
        colorScheme = scheme,
        typography = Typography(),
        content = content,
    )
}
