package pl.synchrofazotron.core.net

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.timeout
import io.ktor.client.request.get
import io.ktor.client.request.parameter
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Typed client for the Synchrofazotron panel (http://<host>:8787). The panel
 * is CORS-open and unauthenticated (lives behind Tailscale/LAN). Slice 0 only
 * needs /healthz and /api/status; more endpoints land in later slices.
 */
class PanelClient(private val baseUrl: String) {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    private val http = HttpClient(OkHttp) {
        expectSuccess = false
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            requestTimeoutMillis = 6_000
            connectTimeoutMillis = 4_000
            socketTimeoutMillis = 6_000
        }
    }

    /** Liveness probe — returns true when the panel answers "ok". */
    suspend fun health(): Boolean = runCatching {
        http.get("$baseUrl/healthz").bodyAsText().trim() == "ok"
    }.getOrDefault(false)

    /** GET /api/status — the main poll. */
    suspend fun status(): StatusResponse = http.get("$baseUrl/api/status").body()

    /** GET /api/volume — per-source current volume. */
    suspend fun volume(): VolumeState = http.get("$baseUrl/api/volume").body()

    /** POST /api/control — play/pause/next/prev a source. */
    suspend fun control(source: String, action: String) {
        http.post("$baseUrl/api/control") {
            contentType(ContentType.Application.Json)
            setBody(ControlRequest(source, action))
        }
    }

    /** POST /api/volume — absolute value or signed delta on a source. */
    suspend fun setVolume(source: String, value: Int? = null, delta: Int? = null) {
        http.post("$baseUrl/api/volume") {
            contentType(ContentType.Application.Json)
            setBody(VolumeRequest(source, value, delta))
        }
    }

    // --- Wi-Fi -----------------------------------------------------------
    suspend fun wifi(): WifiInfo = http.get("$baseUrl/api/wifi").body()

    /** GET /api/wifi/scan — blocks up to ~25 s server-side. */
    suspend fun wifiScan(): WifiScan = http.get("$baseUrl/api/wifi/scan") {
        timeout { requestTimeoutMillis = 35_000; socketTimeoutMillis = 35_000 }
    }.body()

    suspend fun wifiAdd(ssid: String, key: String): OkMessage =
        http.post("$baseUrl/api/wifi/add") {
            contentType(ContentType.Application.Json)
            setBody(WifiAddRequest(ssid, key))
        }.body()

    suspend fun wifiRemove(slot: Int): OkMessage =
        http.post("$baseUrl/api/wifi/remove") {
            contentType(ContentType.Application.Json)
            setBody(SlotRequest(slot))
        }.body()

    // --- Bluetooth -------------------------------------------------------
    suspend fun bt(): BtInfo = http.get("$baseUrl/api/bt").body()

    suspend fun pair(): PairResponse = http.post("$baseUrl/api/pair").body()

    /** POST /api/bt/connect — blocks up to ~25 s server-side. */
    suspend fun btConnect(mac: String): OkMessage =
        http.post("$baseUrl/api/bt/connect") {
            contentType(ContentType.Application.Json)
            setBody(MacRequest(mac))
            timeout { requestTimeoutMillis = 35_000; socketTimeoutMillis = 35_000 }
        }.body()

    suspend fun btDisconnect(mac: String): OkMessage =
        http.post("$baseUrl/api/bt/disconnect") {
            contentType(ContentType.Application.Json)
            setBody(MacRequest(mac))
        }.body()

    suspend fun btForget(mac: String): OkMessage =
        http.post("$baseUrl/api/bt/forget") {
            contentType(ContentType.Application.Json)
            setBody(MacRequest(mac))
        }.body()

    // --- Audio -----------------------------------------------------------
    suspend fun audio(): AudioState = http.get("$baseUrl/api/audio").body()

    suspend fun audioSet(output: String): OkMessage =
        http.post("$baseUrl/api/audio/set") {
            contentType(ContentType.Application.Json)
            setBody(OutputRequest(output))
        }.body()

    /** POST /api/audio/test — plays a test tone, blocks up to ~15 s. */
    suspend fun audioTest(): OkMessage =
        http.post("$baseUrl/api/audio/test") {
            timeout { requestTimeoutMillis = 25_000; socketTimeoutMillis = 25_000 }
        }.body()

    // --- System ----------------------------------------------------------
    suspend fun setName(name: String): OkMessage =
        http.post("$baseUrl/api/name") {
            contentType(ContentType.Application.Json)
            setBody(NameRequest(name))
        }.body()

    suspend fun tailscale(): TailscaleState = http.get("$baseUrl/api/tailscale").body()

    suspend fun tailscaleSet(up: Boolean): OkMessage =
        http.post("$baseUrl/api/tailscale/set") {
            contentType(ContentType.Application.Json)
            setBody(UpRequest(up))
        }.body()

    suspend fun updateStatus(): UpdateState = http.get("$baseUrl/api/update").body()

    /** GET /api/update/check — compares against GitHub, blocks up to ~15 s. */
    suspend fun updateCheck(): UpdateCheck = http.get("$baseUrl/api/update/check") {
        timeout { requestTimeoutMillis = 25_000; socketTimeoutMillis = 25_000 }
    }.body()

    suspend fun updateRun(): OkMessage = http.post("$baseUrl/api/update/run").body()

    suspend fun reboot() {
        http.post("$baseUrl/api/reboot")
    }

    // --- Visualizer ------------------------------------------------------
    suspend fun viz(): VizState = http.get("$baseUrl/api/viz").body()

    suspend fun vizToggle(): OkMessage = http.post("$baseUrl/api/viz/toggle").body()

    suspend fun vizEngine(engine: String, shader: String = ""): OkMessage =
        http.post("$baseUrl/api/viz/engine") {
            contentType(ContentType.Application.Json)
            setBody(VizEngineRequest(engine, shader))
        }.body()

    suspend fun vizPreset(name: String): OkMessage =
        http.post("$baseUrl/api/viz/preset") {
            contentType(ContentType.Application.Json)
            setBody(VizPresetRequest(name))
        }.body()

    suspend fun vizScale(scale: String): OkMessage =
        http.post("$baseUrl/api/viz/scale") {
            contentType(ContentType.Application.Json)
            setBody(VizScaleRequest(scale))
        }.body()

    // --- LMS radio / favorites -------------------------------------------
    suspend fun lmsRadio(): LmsList = http.get("$baseUrl/api/lms/radio").body()

    suspend fun lmsRadioBrowse(verb: String, itemId: String): LmsList =
        http.get("$baseUrl/api/lms/radio/browse") {
            parameter("verb", verb)
            parameter("item_id", itemId)
        }.body()

    suspend fun lmsRadioSearch(q: String): LmsList =
        http.get("$baseUrl/api/lms/radio/search") { parameter("q", q) }.body()

    suspend fun lmsFavorites(itemId: String = ""): LmsList =
        http.get("$baseUrl/api/lms/favorites") { parameter("item_id", itemId) }.body()

    suspend fun lmsRadioPlay(verb: String, itemId: String, add: Boolean = false): OkResp =
        http.post("$baseUrl/api/lms/radio/play") {
            contentType(ContentType.Application.Json)
            setBody(RadioPlayRequest(verb, itemId, add))
        }.body()

    suspend fun lmsPlayUrl(url: String, title: String): OkResp =
        http.post("$baseUrl/api/lms/playurl") {
            contentType(ContentType.Application.Json)
            setBody(PlayUrlRequest(url, title))
        }.body()

    suspend fun lmsFavPlay(id: String, url: String, title: String): OkResp =
        http.post("$baseUrl/api/lms/favorites/play") {
            contentType(ContentType.Application.Json)
            setBody(FavPlayRequest(id, url, title))
        }.body()

    suspend fun lmsFavAdd(url: String, title: String, icon: String): OkResp =
        http.post("$baseUrl/api/lms/favorites/add") {
            contentType(ContentType.Application.Json)
            setBody(FavAddRequest(url, title, icon))
        }.body()

    suspend fun lmsFavRemove(id: String): OkResp =
        http.post("$baseUrl/api/lms/favorites/remove") {
            contentType(ContentType.Application.Json)
            setBody(IdRequest(id))
        }.body()

    // --- TIDAL -----------------------------------------------------------
    suspend fun tidal(): TidalState = http.get("$baseUrl/api/tidal").body()

    suspend fun tidalInstall(): OkResp = http.post("$baseUrl/api/tidal/install").body()

    suspend fun tidalAuthStart(): TidalAuthStart = http.post("$baseUrl/api/tidal/auth/start").body()

    suspend fun tidalAuthStatus(code: String): TidalAuthStatus =
        http.get("$baseUrl/api/tidal/auth/status") { parameter("code", code) }.body()

    suspend fun tidalShow(show: Boolean): OkResp =
        http.post("$baseUrl/api/tidal/show") {
            contentType(ContentType.Application.Json)
            setBody(ShowRequest(show))
        }.body()

    suspend fun tidalForget(id: String): OkResp =
        http.post("$baseUrl/api/tidal/forget") {
            contentType(ContentType.Application.Json)
            setBody(IdRequest(id))
        }.body()

    fun close() = http.close()
}

/**
 * Normalises whatever the user typed (host, host:port, ip, full URL) into a
 * canonical base URL: adds http://, defaults the port to 8787, trims slashes.
 */
fun normalizeBaseUrl(input: String): String {
    var h = input.trim()
    if (h.isEmpty()) return h
    if (!h.startsWith("http://") && !h.startsWith("https://")) h = "http://$h"
    h = h.trimEnd('/')
    val afterScheme = h.substringAfter("://")
    // add the default panel port when the host part carries none
    if (!afterScheme.substringBefore('/').contains(':')) h = "$h:8787"
    return h
}
