package pl.synchrofazotron.core.prefs

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.dataStore by preferencesDataStore(name = "synchrofazotron")

/** A device the app has successfully talked to; url is the dedupe key. */
@Serializable
data class KnownDevice(val name: String, val url: String)

/**
 * Local, per-app persistence: the selected device base URL plus the
 * known-devices list the picker shows (most recent first, capped small —
 * mirrors the SPA's `knownDevices` in localStorage). Language and theme
 * join in later slices.
 */
class DeviceStore(private val context: Context) {

    private val baseKey = stringPreferencesKey("base_url")
    private val themeKey = stringPreferencesKey("theme")
    private val knownKey = stringPreferencesKey("known_devices")
    private val json = Json { ignoreUnknownKeys = true }

    val baseUrl: Flow<String?> = context.dataStore.data.map { it[baseKey] }

    /** "system" | "mono-light" | "mono-dark" | "neon". */
    val theme: Flow<String> = context.dataStore.data.map { it[themeKey] ?: "system" }

    suspend fun setBaseUrl(url: String) {
        context.dataStore.edit { it[baseKey] = url }
    }

    suspend fun setTheme(value: String) {
        context.dataStore.edit { it[themeKey] = value }
    }

    suspend fun clear() {
        context.dataStore.edit { it.remove(baseKey) }
    }

    // --- known devices ----------------------------------------------------
    private fun decode(prefs: Preferences): List<KnownDevice> =
        prefs[knownKey]?.let {
            runCatching { json.decodeFromString<List<KnownDevice>>(it) }.getOrNull()
        } ?: emptyList()

    val knownDevices: Flow<List<KnownDevice>> = context.dataStore.data.map(::decode)

    suspend fun rememberDevice(name: String, url: String) {
        context.dataStore.edit { prefs ->
            val next = (listOf(KnownDevice(name, url)) + decode(prefs).filter { it.url != url })
                .take(6)
            prefs[knownKey] = json.encodeToString(next)
        }
    }

    suspend fun forgetDevice(url: String) {
        context.dataStore.edit { prefs ->
            prefs[knownKey] = json.encodeToString(decode(prefs).filter { it.url != url })
        }
    }
}
