package pl.synchrofazotron.core

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pl.synchrofazotron.core.net.PanelClient
import pl.synchrofazotron.core.net.StatusResponse

/**
 * Central live state for one connected device: polls /api/status + /api/volume,
 * and exposes control / volume actions. Shared by the UI and the Activity's
 * hardware-volume-key handler, so both read the same snapshot.
 */
class PanelSession(
    val baseUrl: String,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val client = PanelClient(baseUrl)

    private val _status = MutableStateFlow<StatusResponse?>(null)
    val status: StateFlow<StatusResponse?> = _status.asStateFlow()

    private val _volumes = MutableStateFlow<Map<String, Int>>(emptyMap())
    val volumes: StateFlow<Map<String, Int>> = _volumes.asStateFlow()

    private val _reconnecting = MutableStateFlow(false)
    val reconnecting: StateFlow<Boolean> = _reconnecting.asStateFlow()

    /** A transient 0..100 value to show in the volume overlay (null = hide). */
    private val _volumeHud = MutableStateFlow<Int?>(null)
    val volumeHud: StateFlow<Int?> = _volumeHud.asStateFlow()

    init {
        scope.launch { pollLoop() }
    }

    private suspend fun pollLoop() {
        while (true) {
            val s = withContext(Dispatchers.IO) { runCatching { client.status() }.getOrNull() }
            if (s != null) {
                _status.value = s
                _reconnecting.value = false
            } else if (_status.value != null) {
                _reconnecting.value = true
            }
            val v = withContext(Dispatchers.IO) { runCatching { client.volume() }.getOrNull() }
            if (v != null) _volumes.value = v.volumes
            delay(3_000)
        }
    }

    fun control(source: String, action: String) {
        scope.launch {
            withContext(Dispatchers.IO) { runCatching { client.control(source, action) } }
            refreshSoon()
        }
    }

    /** Hardware-key nudge: optimistic HUD + POST a delta to the primary source. */
    fun nudgeVolume(delta: Int): Boolean {
        val target = primarySource() ?: return false
        val current = _volumes.value[target] ?: 50
        val next = (current + delta).coerceIn(0, 100)
        _volumes.value = _volumes.value.toMutableMap().apply { put(target, next) }
        _volumeHud.value = next
        scope.launch {
            withContext(Dispatchers.IO) { runCatching { client.setVolume(target, delta = delta) } }
            delay(1_200)
            if (_volumeHud.value == next) _volumeHud.value = null
        }
        return true
    }

    fun setVolume(source: String, value: Int) {
        _volumes.value = _volumes.value.toMutableMap().apply { put(source, value.coerceIn(0, 100)) }
        scope.launch {
            withContext(Dispatchers.IO) { runCatching { client.setVolume(source, value = value) } }
        }
    }

    /** The source hardware volume keys act on: a playing controllable source
     *  that exposes a volume, else any controllable one that does. */
    fun primarySource(): String? {
        val s = _status.value ?: return null
        val vol = _volumes.value
        return s.sources.firstOrNull { it.playing && it.controllable && vol.containsKey(it.id) }?.id
            ?: s.sources.firstOrNull { it.controllable && vol.containsKey(it.id) }?.id
            ?: vol.keys.firstOrNull()
    }

    private fun refreshSoon() {
        scope.launch {
            delay(500)
            val s = withContext(Dispatchers.IO) { runCatching { client.status() }.getOrNull() }
            if (s != null) _status.value = s
        }
    }

    // On-demand data (not part of the fast poll) — one shared client, IO-bound.
    suspend fun fetchWifi() = io { client.wifi() }
    suspend fun scanWifi() = io { client.wifiScan() }
    suspend fun addWifi(ssid: String, key: String) = io { client.wifiAdd(ssid, key) }
    suspend fun removeWifi(slot: Int) = io { client.wifiRemove(slot) }
    suspend fun fetchBt() = io { client.bt() }
    suspend fun pair() = io { client.pair() }
    suspend fun btConnect(mac: String) = io { client.btConnect(mac) }
    suspend fun btDisconnect(mac: String) = io { client.btDisconnect(mac) }
    suspend fun btForget(mac: String) = io { client.btForget(mac) }

    private suspend fun <T> io(block: suspend () -> T): T? =
        withContext(Dispatchers.IO) { runCatching { block() }.getOrNull() }

    fun close() {
        client.close()
        scope.cancel()
    }
}
