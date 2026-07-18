package pl.synchrofazotron.ui.radio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SecondaryTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import kotlinx.coroutines.launch
import pl.synchrofazotron.R
import pl.synchrofazotron.core.PanelSession
import pl.synchrofazotron.core.net.LmsItem
import pl.synchrofazotron.core.net.LmsList

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RadioScreen(session: PanelSession, onBack: () -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.radio_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back))
                    }
                },
            )
        },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            SecondaryTabRow(selectedTabIndex = tab) {
                listOf(R.string.radio_browse, R.string.radio_search, R.string.radio_favorites)
                    .forEachIndexed { i, res ->
                        Tab(selected = tab == i, onClick = { tab = i }, text = { Text(stringResource(res)) })
                    }
            }
            when (tab) {
                0 -> BrowseTab(session)
                1 -> SearchTab(session)
                else -> FavoritesTab(session)
            }
        }
    }
}

@Composable
private fun BrowseTab(session: PanelSession) {
    val scope = rememberCoroutineScope()
    val stack = remember { mutableStateListOf<LmsList>() }
    var loading by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        if (stack.isEmpty()) {
            loading = true
            session.lmsRadio()?.let { stack.add(it) }
            loading = false
        }
    }

    val current = stack.lastOrNull()
    Column {
        if (stack.size > 1) {
            TextButton(onClick = { stack.removeAt(stack.lastIndex) }) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, null, Modifier.padding(end = 6.dp))
                Text(current?.title.orEmpty().ifBlank { stringResource(R.string.back) }, maxLines = 1)
            }
        }
        ItemList(
            items = current?.items.orEmpty(),
            loading = loading,
            onOpen = { item ->
                scope.launch {
                    loading = true
                    val verb = item.verb.ifBlank { current?.verb ?: "" }
                    session.lmsRadioBrowse(verb, item.itemId)?.let { stack.add(it) }
                    loading = false
                }
            },
            onPlay = { item ->
                scope.launch { session.lmsRadioPlay(item.verb.ifBlank { current?.verb ?: "" }, item.itemId) }
            },
            onFav = { item -> item.fav?.let { f -> scope.launch { session.lmsFavAdd(f.url, f.title, f.icon) } } },
        )
    }
}

@Composable
private fun SearchTab(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var q by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<LmsList?>(null) }
    var loading by remember { mutableStateOf(false) }

    fun run() {
        if (q.isBlank()) return
        scope.launch { loading = true; result = session.lmsRadioSearch(q.trim()); loading = false }
    }

    Column {
        OutlinedTextField(
            value = q,
            onValueChange = { q = it },
            singleLine = true,
            label = { Text(stringResource(R.string.radio_search_hint)) },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { run() }),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        )
        ItemList(
            items = result?.items.orEmpty(),
            loading = loading,
            onOpen = { }, // search results are flat
            onPlay = { item ->
                scope.launch { session.lmsRadioPlay(item.verb.ifBlank { result?.verb ?: "search" }, item.itemId) }
            },
            onFav = { item -> item.fav?.let { f -> scope.launch { session.lmsFavAdd(f.url, f.title, f.icon) } } },
        )
    }
}

@Composable
private fun FavoritesTab(session: PanelSession) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<LmsList?>(null) }
    var loading by remember { mutableStateOf(false) }

    suspend fun reload() { loading = true; list = session.lmsFavorites(); loading = false }
    LaunchedEffect(Unit) { reload() }

    ItemList(
        items = list?.items.orEmpty(),
        loading = loading,
        onOpen = { item -> scope.launch { loading = true; list = session.lmsFavorites(item.itemId.ifBlank { item.id }); loading = false } },
        onPlay = { item -> scope.launch { session.lmsFavPlay(item.id.ifBlank { item.itemId }, item.url, item.title) } },
        onRemove = { item -> scope.launch { session.lmsFavRemove(item.id.ifBlank { item.itemId }); reload() } },
    )
}

@Composable
private fun ItemList(
    items: List<LmsItem>,
    loading: Boolean,
    onOpen: (LmsItem) -> Unit,
    onPlay: (LmsItem) -> Unit,
    onFav: ((LmsItem) -> Unit)? = null,
    onRemove: ((LmsItem) -> Unit)? = null,
) {
    if (loading && items.isEmpty()) {
        Row(Modifier.fillMaxWidth().padding(24.dp), horizontalArrangement = Arrangement.Center) {
            CircularProgressIndicator()
        }
        return
    }
    if (items.isEmpty()) {
        Text(
            stringResource(R.string.radio_empty),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(24.dp),
        )
        return
    }
    LazyColumn(Modifier.fillMaxSize()) {
        items(items) { item ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { if (item.browsable) onOpen(item) else onPlay(item) }
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = item.title,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodyLarge,
                )
                if (onRemove != null) {
                    IconButton(onClick = { onRemove(item) }) {
                        Icon(Icons.Filled.Star, stringResource(R.string.radio_fav_remove))
                    }
                } else if (onFav != null && item.fav != null) {
                    IconButton(onClick = { onFav(item) }) {
                        Icon(Icons.Filled.StarBorder, stringResource(R.string.radio_fav_add))
                    }
                }
                if (item.browsable) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null)
                } else if (item.playable) {
                    Icon(Icons.Filled.PlayArrow, stringResource(R.string.radio_play))
                }
            }
            HorizontalDivider()
        }
    }
}
