package pl.synchrofazotron.ui.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.style.TextOverflow

/**
 * Segmented pill control matching the web app's mono tab look (an iOS-style
 * segmented control): a filled track with the active segment cut out. Used for
 * the Now/Radio/Viz tabs, the Settings sections, and the viz engine picker.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SegTabs(
    items: List<Pair<String, String>>, // (id, label)
    active: String,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    fillWidth: Boolean = true,
) {
    SingleChoiceSegmentedButtonRow(
        modifier = if (fillWidth) modifier.fillMaxWidth() else modifier,
    ) {
        items.forEachIndexed { i, (id, label) ->
            SegmentedButton(
                selected = id == active,
                onClick = { onChange(id) },
                shape = SegmentedButtonDefaults.itemShape(index = i, count = items.size),
                label = { Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            )
        }
    }
}
