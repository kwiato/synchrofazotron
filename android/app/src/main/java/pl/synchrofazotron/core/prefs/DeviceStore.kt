package pl.synchrofazotron.core.prefs

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "synchrofazotron")

/**
 * Local, per-app persistence. Slice 0 stores just the selected device base
 * URL; language, theme and the known-devices list join it in later slices.
 */
class DeviceStore(private val context: Context) {

    private val baseKey = stringPreferencesKey("base_url")
    private val themeKey = stringPreferencesKey("theme")

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
}
