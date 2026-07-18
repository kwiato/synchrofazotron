package pl.synchrofazotron.ui.theme

import androidx.compose.ui.unit.dp

/**
 * Golden-ratio spacing scale, ported verbatim from the web panel's
 * `--spacer-*` tokens: a geometric ladder with ratio φ (≈1.618) anchored at a
 * 32dp base. Using the same steps keeps the native app's rhythm identical to
 * the original.
 */
object Spacing {
    val xs3 = 4.6.dp    // --spacer-3xs
    val xs2 = 7.5.dp    // --spacer-2xs
    val xs = 12.2.dp    // --spacer-xs
    val sm = 19.8.dp    // --spacer-sm
    val base = 32.dp    // --spacer-base
    val md = 51.8.dp    // --spacer-md
    val lg = 83.8.dp    // --spacer-lg
}
