package pl.synchrofazotron

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import pl.synchrofazotron.ui.App
import pl.synchrofazotron.ui.theme.SynchrofazotronTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SynchrofazotronTheme {
                App()
            }
        }
    }
}
