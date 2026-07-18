package pl.synchrofazotron

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import pl.synchrofazotron.ui.AppRoot

class MainActivity : ComponentActivity() {

    /**
     * Set by the composition when a device with a controllable source is
     * connected. Returns true when it handled the nudge (so we consume the key
     * instead of moving the phone's own media stream). Null / false = let the
     * system handle the volume key normally.
     */
    var volumeKeyHandler: ((delta: Int) -> Boolean)? = null

    private var lastVolumeConsumed = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AppRoot()
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        val delta = when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> 5
            KeyEvent.KEYCODE_VOLUME_DOWN -> -5
            else -> return super.onKeyDown(keyCode, event)
        }
        lastVolumeConsumed = volumeKeyHandler?.invoke(delta) == true
        return if (lastVolumeConsumed) true else super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP || keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {
            if (lastVolumeConsumed) {
                lastVolumeConsumed = false
                return true
            }
        }
        return super.onKeyUp(keyCode, event)
    }
}
