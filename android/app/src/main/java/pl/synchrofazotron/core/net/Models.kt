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

/** Generic mutating-endpoint envelope. Branch on [ok]; [message] is device-
 *  localized display text, used only as a detail line. */
@Serializable
data class OkMessage(val ok: Boolean = false, val message: String = "")

// --- Wi-Fi ---------------------------------------------------------------
@Serializable
data class WifiInfo(
    val iface: String = "",
    val current: WifiCurrent? = null,
    val saved: List<WifiSaved> = emptyList(),
    @SerialName("free_slots") val freeSlots: Int = 0,
    val hostname: String = "",
    @SerialName("tailscale_ip") val tailscaleIp: String = "",
)

@Serializable
data class WifiCurrent(val ssid: String = "", val signal: Int? = null, val ip: String = "")

@Serializable
data class WifiSaved(val slot: Int = 0, val ssid: String = "", val keymgr: String = "")

@Serializable
data class WifiScan(val networks: List<WifiNetwork> = emptyList())

@Serializable
data class WifiNetwork(val ssid: String = "", val signal: Int = 0)

@Serializable
data class WifiAddRequest(val ssid: String, val key: String)

@Serializable
data class SlotRequest(val slot: Int)

// --- Bluetooth -----------------------------------------------------------
@Serializable
data class BtInfo(
    val paired: List<BtDevice> = emptyList(),
    val reconnect: BtReconnect = BtReconnect(),
)

@Serializable
data class BtDevice(val mac: String = "", val name: String = "", val connected: Boolean = false)

@Serializable
data class BtReconnect(val enabled: Boolean = false, val interval: Int = 45)

@Serializable
data class MacRequest(val mac: String)

@Serializable
data class PairResponse(val ok: Boolean = false, val seconds: Int = 0)

// --- Audio ---------------------------------------------------------------
@Serializable
data class AudioState(
    val output: String = "",
    val running: String = "",
    val overlay: String = "",
    val cards: Map<String, Boolean> = emptyMap(),
    @SerialName("hdmi_connected") val hdmiConnected: Boolean = false,
    @SerialName("bridge_active") val bridgeActive: Boolean = false,
    @SerialName("reboot_required") val rebootRequired: Boolean = false,
)

@Serializable
data class OutputRequest(val output: String)

// --- System / Tailscale / updates ---------------------------------------
@Serializable
data class TailscaleState(val installed: Boolean = false, val active: Boolean = false, val ip: String = "")

@Serializable
data class UpdateState(val running: Boolean = false, val failed: Boolean = false)

@Serializable
data class UpdateCheck(
    val ok: Boolean = false,
    @SerialName("update_available") val updateAvailable: Boolean = false,
)

@Serializable
data class NameRequest(val name: String)

@Serializable
data class UpRequest(val up: Boolean)

// --- Visualizer ----------------------------------------------------------
@Serializable
data class VizState(
    val installed: Boolean = false,
    val active: Boolean = false,
    val enabled: Boolean = false,
    @SerialName("hdmi_connected") val hdmiConnected: Boolean = false,
    val preset: String = "",
    val engine: String = "cava",
    val shader: String = "",
    val scale: String = "",
    val scales: List<String> = emptyList(),
    @SerialName("glsl_available") val glslAvailable: Boolean = false,
    @SerialName("glsl_error") val glslError: String = "",
    val presets: List<VizPreset> = emptyList(),
    val shaders: List<VizShader> = emptyList(),
)

@Serializable
data class VizPreset(val id: String = "", val label: String = "")

@Serializable
data class VizShader(val id: String = "", val label: String = "")

@Serializable
data class VizPresetRequest(val name: String)

@Serializable
data class VizEngineRequest(val engine: String, val shader: String = "")

@Serializable
data class VizScaleRequest(val scale: String)
