package pl.synchrofazotron.ui.panel

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.border
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.VizState
import pl.synchrofazotron.ui.components.Eq
import pl.synchrofazotron.ui.components.SegTabs
import pl.synchrofazotron.ui.components.primarySource
import pl.synchrofazotron.ui.components.srcSub
import pl.synchrofazotron.ui.radio.RadioTab
import pl.synchrofazotron.ui.theme.Spacing
import java.net.URLEncoder

@Composable
fun PanelScreen(session: PanelSession, onOpenStudio: () -> Unit) {
    val tabs = listOf(
        "now" to stringResource(R.string.tab_now),
        "radio" to stringResource(R.string.tab_radio),
        "viz" to stringResource(R.string.tab_viz),
    )
    val pager = rememberPagerState(pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    Column(Modifier.fillMaxSize()) {
        SegTabs(
            items = tabs,
            active = tabs[pager.currentPage].first,
            onChange = { id ->
                val idx = tabs.indexOfFirst { it.first == id }
                if (idx >= 0) scope.launch { pager.animateScrollToPage(idx) }
            },
            modifier = Modifier.padding(horizontal = Spacing.xs, vertical = Spacing.xs2),
        )
        HorizontalPager(state = pager, modifier = Modifier.weight(1f)) { page ->
            when (page) {
                0 -> NowTab(session)
                1 -> RadioTab(session)
                else -> VizTab(session, onOpenStudio)
            }
        }
    }
}

@Composable
private fun NowTab(session: PanelSession) {
    val status by session.status.collectAsStateWithLifecycle()
    val p = primarySource(status)
    val playing = p?.playing == true

    // Cover shows whenever LMS has a current track — playing OR paused/idle,
    // not only while playing (otherwise the square reads as an empty void).
    val hasTrack = p?.id == "lms" && p.detail.isNotBlank() && status?.lmsPlayerId?.isNotBlank() == true
    val artUrl = if (hasTrack) {
        val inner = "/music/current/cover.jpg?player=${status!!.lmsPlayerId}&_t=${p!!.detail}"
        "${session.baseUrl}/api/lms/art?path=" + URLEncoder.encode(inner, "UTF-8")
    } else null

    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = Spacing.base),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if ((status?.playingCount ?: 0) >= 2) {
            Card(Modifier.fillMaxWidth().padding(bottom = Spacing.xs)) {
                Text(
                    stringResource(R.string.now_multi_warning),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(12.dp),
                )
            }
        }
        Box(
            modifier = Modifier
                .fillMaxWidth(0.62f)
                .aspectRatio(1f)
                .clip(RoundedCornerShape(22.dp))
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(22.dp)),
            contentAlignment = Alignment.Center,
        ) {
            // Placeholder underneath: animated EQ while playing, a calm music
            // note when idle. Real art (when present) paints over it.
            if (playing) {
                Eq(on = true, modifier = Modifier.fillMaxWidth(0.28f))
            } else {
                Icon(
                    Icons.Rounded.MusicNote,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.fillMaxWidth(0.3f).aspectRatio(1f),
                )
            }
            if (artUrl != null) {
                AsyncImage(
                    model = artUrl,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
        Text(
            text = p?.let { it.detail.ifBlank { it.name } } ?: stringResource(R.string.now_nothing),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = Spacing.sm),
        )
        if (p != null) {
            Text(
                text = srcSub(p),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = Spacing.xs3),
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VizTab(session: PanelSession, onOpenStudio: () -> Unit) {
    val scope = rememberCoroutineScope()
    var viz by remember { mutableStateOf<VizState?>(null) }
    suspend fun reload() { viz = session.fetchViz() }
    LaunchedEffect(session) { reload() }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
    ) {
        val v = viz
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(stringResource(R.string.tab_viz), style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    if (v?.installed == true) {
                        Switch(checked = v.active, onCheckedChange = { scope.launch { session.vizToggle(); reload() } })
                    }
                }
                when {
                    v == null -> Text("…", modifier = Modifier.padding(top = 12.dp))
                    !v.installed -> Text(stringResource(R.string.viz_not_installed),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 12.dp))
                    else -> {
                        SegTabs(
                            items = listOf(
                                "cava" to stringResource(R.string.viz_engine_cava),
                                "glsl" to stringResource(R.string.viz_engine_glsl),
                            ),
                            active = v.engine,
                            onChange = { eng ->
                                scope.launch { session.vizEngine(eng, if (eng == "glsl") v.shader else ""); reload() }
                            },
                            modifier = Modifier.padding(top = 12.dp),
                        )
                        val items = if (v.engine == "glsl") v.shaders.map { it.id to it.label } else v.presets.map { it.id to it.label }
                        val current = if (v.engine == "glsl") v.shader else v.preset
                        FlowRow(
                            modifier = Modifier.padding(top = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items.forEach { (id, label) ->
                                FilterChip(
                                    selected = id == current,
                                    onClick = {
                                        scope.launch {
                                            if (v.engine == "glsl") session.vizEngine("glsl", id) else session.vizPreset(id)
                                            reload()
                                        }
                                    },
                                    label = { Text(label) },
                                )
                            }
                        }
                        OutlinedButton(onClick = onOpenStudio, modifier = Modifier.padding(top = 8.dp)) {
                            Text(stringResource(R.string.viz_studio))
                        }
                    }
                }
            }
        }
    }
}
