package pl.synchrofazotron.core.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import pl.synchrofazotron.BuildConfig
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * In-app self-update for the sideload channel — the native app's own updater
 * (separate from the panel/system update). It reads the rolling GitHub release
 * "android-native-latest" (its body is the build SHA, set by CI), compares to
 * this build's SHA, downloads the APK and hands it to the system installer.
 *
 * Every CI build shares one committed debug keystore, so an in-place update
 * works once the user is past the first key transition.
 */
object AppUpdater {
    private const val REPO = "kwiato/synchrofazotron"
    private const val TAG = "android-native-latest"
    const val APK_URL = "https://github.com/$REPO/releases/download/$TAG/native-debug.apk"
    private const val RELEASE_API = "https://api.github.com/repos/$REPO/releases/tags/$TAG"

    /** Short SHA this build was compiled from ("dev" for local builds). */
    val currentSha: String get() = BuildConfig.GIT_SHA.take(7)

    /** Latest published short SHA (from the release body), or null on error. */
    suspend fun latestSha(): String? = withContext(Dispatchers.IO) {
        runCatching {
            val conn = (URL(RELEASE_API).openConnection() as HttpURLConnection).apply {
                setRequestProperty("Accept", "application/vnd.github+json")
                connectTimeout = 8_000
                readTimeout = 8_000
            }
            conn.inputStream.bufferedReader().use { r ->
                val body = JSONObject(r.readText()).optString("body", "")
                Regex("[0-9a-f]{7,40}").find(body)?.value?.take(7)
            }
        }.getOrNull()
    }

    /** true / false / null(unknown). A local dev build ("dev") reads as update-available. */
    suspend fun updateAvailable(): Boolean? {
        val latest = latestSha() ?: return null
        return latest != currentSha
    }

    /** Streams the APK into cacheDir, reporting 0..100 progress. */
    suspend fun download(context: Context, onProgress: (Int) -> Unit): File? =
        withContext(Dispatchers.IO) {
            runCatching {
                val conn = (URL(APK_URL).openConnection() as HttpURLConnection).apply {
                    instanceFollowRedirects = true
                    connectTimeout = 15_000
                    readTimeout = 30_000
                }
                val total = conn.contentLengthLong
                val file = File(context.cacheDir, "update.apk")
                conn.inputStream.use { input ->
                    file.outputStream().use { out ->
                        val buf = ByteArray(64 * 1024)
                        var read = 0L
                        var n: Int
                        while (input.read(buf).also { n = it } >= 0) {
                            out.write(buf, 0, n)
                            read += n
                            if (total > 0) onProgress(((read * 100) / total).toInt())
                        }
                    }
                }
                file
            }.getOrNull()
        }

    fun canInstall(context: Context): Boolean =
        context.packageManager.canRequestPackageInstalls()

    fun openInstallSettings(context: Context) {
        context.startActivity(
            Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    fun install(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
