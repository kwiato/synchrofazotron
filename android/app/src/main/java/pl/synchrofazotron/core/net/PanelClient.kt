package pl.synchrofazotron.core.net

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.statement.bodyAsText
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
