package pl.synchrofazotron.core.net

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import java.net.Inet4Address

/** A panel found over mDNS, resolved down to a usable numeric IPv4. */
data class DiscoveredPanel(val name: String, val ip: String, val port: Int) {
    val url: String get() = "http://$ip:$port"
}

/**
 * mDNS discovery of `_pistream._tcp` panels (advertised by avahi on the
 * device — see web/install.sh). Mirror of the SPA's discovery.js, including
 * its rule: only a service resolved to a numeric IPv4 makes a row — if
 * resolution never happens (Android NSD is flaky with a VPN up), an empty
 * list plus manual entry beats a row that always fails.
 */
class PanelDiscovery(context: Context) {
    private val nsd = context.getSystemService(NsdManager::class.java)

    /** Emits the current de-duplicated device list on every change. Collection
     *  starts discovery; cancellation stops it. */
    fun watch(): Flow<List<DiscoveredPanel>> = callbackFlow {
        // Keyed by service name so a re-announcing device updates in place.
        val found = LinkedHashMap<String, DiscoveredPanel>()
        // NsdManager runs a single resolve at a time — everything found while
        // one is in flight waits its turn here.
        val queue = ArrayDeque<NsdServiceInfo>()
        var resolving = false

        fun emit() { trySend(found.values.toList()) }

        fun resolveNext() {
            if (resolving) return
            val svc = queue.removeFirstOrNull() ?: return
            resolving = true
            // resolveService is deprecated (API 34's registerServiceInfoCallback
            // replaces it) but still the only call that works from minSdk 26.
            @Suppress("DEPRECATION")
            nsd.resolveService(svc, object : NsdManager.ResolveListener {
                override fun onResolveFailed(s: NsdServiceInfo, error: Int) {
                    resolving = false
                    resolveNext()
                }

                override fun onServiceResolved(s: NsdServiceInfo) {
                    val ip = (s.host as? Inet4Address)?.hostAddress
                    if (ip != null) {
                        val port = if (s.port > 0) s.port else 8787
                        found[s.serviceName] = DiscoveredPanel(s.serviceName, ip, port)
                        emit()
                    }
                    resolving = false
                    resolveNext()
                }
            })
        }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(type: String) {}
            override fun onDiscoveryStopped(type: String) {}
            override fun onStartDiscoveryFailed(type: String, error: Int) { close() }
            override fun onStopDiscoveryFailed(type: String, error: Int) {}

            override fun onServiceFound(s: NsdServiceInfo) {
                queue.addLast(s)
                resolveNext()
            }

            override fun onServiceLost(s: NsdServiceInfo) {
                if (found.remove(s.serviceName) != null) emit()
            }
        }

        nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        awaitClose { runCatching { nsd.stopServiceDiscovery(listener) } }
    }

    private companion object {
        const val SERVICE_TYPE = "_pistream._tcp."
    }
}
