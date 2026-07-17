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

/** GET /api/volume — per-source 0..100; a key is absent when not controllable. */
@Serializable
data class VolumeState(
    val volumes: Map<String, Int> = emptyMap(),
)

@Serializable
data class ControlRequest(val source: String, val action: String)

@Serializable
data class VolumeRequest(
    val source: String,
    val value: Int? = null,
    val delta: Int? = null,
)
