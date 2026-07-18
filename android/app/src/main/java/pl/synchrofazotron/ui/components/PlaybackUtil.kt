package pl.synchrofazotron.ui.components

import pl.synchrofazotron.core.net.Source
import pl.synchrofazotron.core.net.StatusResponse

/** The source the player bar and Now tab follow: first playing, else first known. */
fun primarySource(status: StatusResponse?): Source? =
    status?.sources?.firstOrNull { it.playing } ?: status?.sources?.firstOrNull()

/** Subtitle under the track name: artist (LMS) · "name — state" or just state. */
fun srcSub(p: Source): String {
    val bits = mutableListOf<String>()
    if (p.artist.isNotBlank()) bits.add(p.artist)
    bits.add(if (p.detail.isNotBlank()) "${p.name} — ${p.state}" else p.state)
    return bits.joinToString(" · ")
}
