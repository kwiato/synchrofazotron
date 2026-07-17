package pl.synchrofazotron.core.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Subset of GET /api/status we render in Slice 0. Unknown keys are ignored by
 * the Json config, so the full payload deserializes fine as this grows.
 */
@Serializable
data class StatusResponse(
    @SerialName("device_name") val deviceName: String = "",
    val lang: String = "en",
    @SerialName("wifi_ssid") val wifiSsid: String = "",
    @SerialName("pair_seconds_left") val pairSecondsLeft: Int = 0,
    val sources: List<Source> = emptyList(),
    @SerialName("playing_count") val playingCount: Int = 0,
)

@Serializable
data class Source(
    val name: String = "",
    val playing: Boolean = false,
    val state: String = "",
    val detail: String = "",
    val artist: String = "",
    val id: String = "",
    val controllable: Boolean = false,
)
