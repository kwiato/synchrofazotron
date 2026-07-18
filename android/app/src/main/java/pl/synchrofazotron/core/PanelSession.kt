package pl.synchrofazotron.core

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pl.synchrofazotron.core.net.OkMessage
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

    /** Transient feedback message (the Droplet), from mutating-endpoint replies. */
    private val _notice = MutableStateFlow<String?>(null)
    val notice: StateFlow<String?> = _notice.asStateFlow()
    private var noticeJob: Job? = null

    fun postNotice(msg: String?) {
        if (msg.isNullOrBlank()) return
        _notice.value = msg
        noticeJob?.cancel()
        noticeJob = scope.launch { delay(3500); _notice.value = null }
    }

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

    /** Immediate status + volume fetch (pull-to-refresh). */
    suspend fun refreshNow() {
        val s = io { client.status() }
        if (s != null) { _status.value = s; _reconnecting.value = false }
        val v = io { client.volume() }
        if (v != null) _volumes.value = v.volumes
    }

    // On-demand data (not part of the fast poll) — one shared client, IO-bound.
    suspend fun fetchWifi() = io { client.wifi() }
    suspend fun scanWifi() = io { client.wifiScan() }
    suspend fun addWifi(ssid: String, key: String) = notify { client.wifiAdd(ssid, key) }
    suspend fun removeWifi(slot: Int) = notify { client.wifiRemove(slot) }
    suspend fun fetchBt() = io { client.bt() }
    suspend fun pair() = io { client.pair() }
    suspend fun btConnect(mac: String) = notify { client.btConnect(mac) }
    suspend fun btDisconnect(mac: String) = notify { client.btDisconnect(mac) }
    suspend fun btForget(mac: String) = notify { client.btForget(mac) }
    suspend fun fetchAudio() = io { client.audio() }
    suspend fun setAudio(output: String) = notify { client.audioSet(output) }
    suspend fun testAudio() = notify { client.audioTest() }
    suspend fun setName(name: String) = notify { client.setName(name) }
    suspend fun fetchTailscale() = io { client.tailscale() }
    suspend fun setTailscale(up: Boolean) = notify { client.tailscaleSet(up) }
    suspend fun updateStatus() = io { client.updateStatus() }
    suspend fun updateCheck() = io { client.updateCheck() }
    suspend fun updateRun() = notify { client.updateRun() }
    suspend fun reboot() = io { client.reboot() }
    suspend fun fetchViz() = io { client.viz() }
    suspend fun vizToggle() = notify { client.vizToggle() }
    suspend fun vizEngine(engine: String, shader: String = "") = notify { client.vizEngine(engine, shader) }
    suspend fun vizPreset(name: String) = notify { client.vizPreset(name) }
    suspend fun vizScale(scale: String) = notify { client.vizScale(scale) }
    suspend fun lmsRadio() = io { client.lmsRadio() }
    suspend fun lmsRadioBrowse(verb: String, itemId: String) = io { client.lmsRadioBrowse(verb, itemId) }
    suspend fun lmsRadioSearch(q: String) = io { client.lmsRadioSearch(q) }
    suspend fun lmsFavorites(itemId: String = "") = io { client.lmsFavorites(itemId) }
    suspend fun lmsRadioPlay(verb: String, itemId: String, add: Boolean = false) = io { client.lmsRadioPlay(verb, itemId, add) }
    suspend fun lmsPlayUrl(url: String, title: String) = io { client.lmsPlayUrl(url, title) }
    suspend fun lmsFavPlay(id: String, url: String, title: String) = io { client.lmsFavPlay(id, url, title) }
    suspend fun lmsFavAdd(url: String, title: String, icon: String) = io { client.lmsFavAdd(url, title, icon) }
    suspend fun lmsFavRemove(id: String) = io { client.lmsFavRemove(id) }
    suspend fun tidal() = io { client.tidal() }
    suspend fun tidalInstall() = io { client.tidalInstall() }
    suspend fun tidalAuthStart() = io { client.tidalAuthStart() }
    suspend fun tidalAuthStatus(code: String) = io { client.tidalAuthStatus(code) }
    suspend fun tidalShow(show: Boolean) = io { client.tidalShow(show) }
    suspend fun tidalForget(id: String) = io { client.tidalForget(id) }

    private suspend fun <T> io(block: suspend () -> T): T? =
        withContext(Dispatchers.IO) { runCatching { block() }.getOrNull() }

    /** io() that also surfaces the reply's localized message as a Droplet. */
    private suspend fun notify(block: suspend () -> OkMessage): OkMessage? {
        val r = io(block)
        postNotice(r?.message)
        return r
    }

    fun close() {
        client.close()
        scope.cancel()
    }
}
