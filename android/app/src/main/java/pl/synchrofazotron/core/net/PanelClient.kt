package pl.synchrofazotron.core.net

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.timeout
import io.ktor.client.request.get
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
