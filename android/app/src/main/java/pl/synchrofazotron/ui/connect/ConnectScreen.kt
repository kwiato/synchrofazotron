package pl.synchrofazotron.ui.connect

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.material3.Scaffold
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.safeDrawing
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pl.synchrofazotron.R
import pl.synchrofazotron.core.net.PanelClient
import pl.synchrofazotron.core.net.normalizeBaseUrl
import androidx.compose.ui.res.stringResource

@Composable
fun ConnectScreen(onConnected: (String) -> Unit) {
    var host by remember { mutableStateOf("") }
    var checking by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun attempt() {
        if (checking || host.isBlank()) return
        error = null
        checking = true
        val url = normalizeBaseUrl(host)
        scope.launch {
            val ok = withContext(Dispatchers.IO) {
                val c = PanelClient(url)
                try { c.health() } finally { c.close() }
            }
            checking = false
            if (ok) onConnected(url) else error = "unreachable"
        }
    }

    Scaffold(contentWindowInsets = WindowInsets.safeDrawing) { pad ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(pad)
                .padding(horizontal = 24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = stringResource(R.string.connect_title),
                style = MaterialTheme.typography.headlineSmall,
            )
            OutlinedTextField(
                value = host,
                onValueChange = { host = it; error = null },
                label = { Text(stringResource(R.string.connect_host_label)) },
                placeholder = { Text(stringResource(R.string.connect_host_hint)) },
                singleLine = true,
                enabled = !checking,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(onGo = { attempt() }),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 24.dp),
            )
            if (error != null) {
                Text(
                    text = stringResource(R.string.connect_unreachable),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
            Button(
                onClick = { attempt() },
                enabled = !checking && host.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 20.dp),
            ) {
                if (checking) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier
                            .padding(end = 8.dp)
                            .size(18.dp),
                    )
                    Text(stringResource(R.string.connect_checking))
                } else {
                    Text(stringResource(R.string.connect_button))
                }
            }
        }
    }
}
