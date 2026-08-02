package pl.synchrofazotron.core.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/** The panel's fixed address while the device runs its fallback setup AP. */
const val SETUP_BASE_URL = "http://192.168.4.1:8787"

/**
 * Detects the fallback setup AP (ap-fallback/ on the device): the phone has
 * joined Synchrofazotron-Setup and the panel answers at 192.168.4.1.
 *
 * All traffic has to go through the Wi-Fi [Network] object explicitly: the AP
 * has no internet, so with mobile data on, Android keeps the default route on
 * cellular and plain sockets would never reach 192.168.4.1. The probe uses
 * Network.openConnection; once setup mode is entered the whole process is
 * bound to the Wi-Fi network so the regular PanelClient stack works unchanged.
 */
class SetupModeDetector(context: Context) {
    private val cm = context.getSystemService(ConnectivityManager::class.java)

    @Volatile private var wifi: Network? = null

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { wifi = network }
        override fun onLost(network: Network) { if (wifi == network) wifi = null }
    }

    init {
        cm.registerNetworkCallback(
            NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .build(),
            callback,
        )
    }

    /** True when the current Wi-Fi looks like the setup AP and the panel
     *  answers /healthz on it. Networks with validated internet are skipped —
     *  a normal LAN never gets probed for 192.168.4.1. */
    suspend fun probe(): Boolean = withContext(Dispatchers.IO) {
        val net = wifi ?: return@withContext false
        val caps = cm.getNetworkCapabilities(net) ?: return@withContext false
        if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
            return@withContext false
        }
        runCatching {
            val conn = net.openConnection(URL("$SETUP_BASE_URL/healthz")) as HttpURLConnection
            conn.connectTimeout = 1_500
            conn.readTimeout = 1_500
            try {
                conn.inputStream.bufferedReader().use { it.readText() }.trim() == "ok"
            } finally {
                conn.disconnect()
            }
        }.getOrDefault(false)
    }

    /** Route the whole app through the (internet-less) setup Wi-Fi. */
    fun bindToWifi() { cm.bindProcessToNetwork(wifi) }

    fun unbind() { cm.bindProcessToNetwork(null) }

    fun close() {
        runCatching { cm.unregisterNetworkCallback(callback) }
        unbind()
    }
}
