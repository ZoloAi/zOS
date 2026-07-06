# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/expansion/shorthand_element_expanders.py

"""
Shorthand Element Expanders
============================

Individual expansion methods for each shorthand element type.
Extracted from shorthand_expander.py to reduce file size.
"""

from zOS import Any, Dict, Optional
from ..dispatch_constants import KEY_ZDISPLAY


def _parse_code_fence(content: str):
    """Parse a markdown code fence string into (language, code_body).

    Strips the opening ``` + optional language tag and the closing ```,
    returning (language_str_or_None, stripped_code_body).
    """
    lines = content.strip().split('\n')
    if not lines:
        return None, content

    first = lines[0].strip()
    if first.startswith('```'):
        language = first[3:].strip() or None
        body_lines = lines[1:]
        # Strip closing fence if present
        if body_lines and body_lines[-1].strip() == '```':
            body_lines = body_lines[:-1]
        return language, '\n'.join(body_lines)

    return None, content


class ShorthandElementExpanders:
    """Mixin providing individual element expansion methods."""

    logger: Any

    def _expand_zheader(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zH0-zH6 to header event."""
        indent_level = int(key[2])
        if self.logger:
            self.logger.info(f"[ShorthandExpander] _expand_zheader: key={key}, indent_level={indent_level}")
        if 0 <= indent_level <= 6:
            return {KEY_ZDISPLAY: {'event': 'header', 'indent': indent_level, **value}}
        return value

    def _expand_ztext(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zText to text event."""
        return {KEY_ZDISPLAY: {'event': 'text', **value}}

    def _expand_zmd(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zMD to rich_text event."""
        return {KEY_ZDISPLAY: {'event': 'rich_text', **value}}

    def _expand_zcode(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zCode to code event, parsing fence syntax if present.

        Shorthand:  zCode: ```python\\n  code\\n  ```
        Longhand:   zCode: {content: '...', language: 'python'}
        """
        content = value.get('content', '')
        if isinstance(content, str) and content.strip().startswith('```'):
            language, clean = _parse_code_fence(content)
            result = {k: v for k, v in value.items() if k != 'content'}
            result['content'] = clean
            if language and 'language' not in result:
                result['language'] = language
            return {KEY_ZDISPLAY: {'event': 'code', **result}}
        return {KEY_ZDISPLAY: {'event': 'code', **value}}

    def _expand_zimage(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zImage to image event."""
        return {KEY_ZDISPLAY: {'event': 'image', **value}}

    def _expand_zvideo(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zVideo to video event.

        Shorthand for the longhand SSOT (`zDisplay: {event: video, ...}` →
        MediaEvents.video). Defaults (open_prompt=True) live on the handler, so
        the shorthand only stamps the event name.
        """
        return {KEY_ZDISPLAY: {'event': 'video', **value}}

    def _expand_zembed(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zEmbed to embed event (media sibling of image/video).

        Shorthand for the longhand SSOT (`zDisplay: {event: embed, ...}` →
        MediaEvents.embed). Defaults (open_prompt=True) live on the handler, so
        the shorthand only stamps the event name.
        """
        return {KEY_ZDISPLAY: {'event': 'embed', **value}}

    def _expand_zurl(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zURL to zURL event."""
        return {KEY_ZDISPLAY: {'event': 'zURL', **value}}

    def _expand_zul(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zUL to list event (bullet style)."""
        if 'zURLs' in value and isinstance(value['zURLs'], dict):
            items = []
            for _, url_value in value['zURLs'].items():
                if isinstance(url_value, dict):
                    items.append({KEY_ZDISPLAY: {'event': 'zURL', **url_value}})
            new_value = {k: v for k, v in value.items() if k != 'zURLs'}
            return {KEY_ZDISPLAY: {'event': 'list', 'style': 'bullet', 'items': items, **new_value}}
        return {KEY_ZDISPLAY: {'event': 'list', 'style': 'bullet', **value}}

    def _expand_zol(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zOL to list event (number style)."""
        if 'zURLs' in value and isinstance(value['zURLs'], dict):
            items = []
            for _, url_value in value['zURLs'].items():
                if isinstance(url_value, dict):
                    items.append({KEY_ZDISPLAY: {'event': 'zURL', **url_value}})
            new_value = {k: v for k, v in value.items() if k != 'zURLs'}
            return {KEY_ZDISPLAY: {'event': 'list', 'style': 'number', 'items': items, **new_value}}
        return {KEY_ZDISPLAY: {'event': 'list', 'style': 'number', **value}}

    def _expand_zdl(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zDL to description list event."""
        return {KEY_ZDISPLAY: {'event': 'dl', **value}}

    def _expand_ztable(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zTable to zTable event."""
        return {KEY_ZDISPLAY: {'event': 'zTable', **value}}

    def _expand_zbtn(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zBtn to button event with defaults."""
        if 'color' not in value:
            value['color'] = 'primary'
        if 'action' not in value:
            value['action'] = '#'
        return {KEY_ZDISPLAY: {'event': 'button', **value}}

    def _expand_zinput(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zInput to read_string event with defaults."""
        if 'type' not in value:
            value['type'] = 'text'
        if 'default' not in value:
            value['default'] = ''
        if 'placeholder' not in value:
            value['placeholder'] = ''
        if 'required' not in value:
            value['required'] = False
        return {KEY_ZDISPLAY: {'event': 'read_string', **value}}

    def _expand_zcheckbox(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zCheckbox to read_bool event with defaults."""
        if 'checked' not in value:
            value['checked'] = False
        if 'required' not in value:
            value['required'] = False
        if 'disabled' not in value:
            value['disabled'] = False
        if 'prompt' not in value:
            value['prompt'] = ''
        return {KEY_ZDISPLAY: {'event': 'read_bool', **value}}

    def _expand_zselect(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zSelect to selection event with defaults."""
        if 'options' not in value:
            value['options'] = []
        if 'multi' not in value:
            value['multi'] = False
        if 'default' not in value:
            value['default'] = None
        if 'prompt' not in value:
            value['prompt'] = ''
        if 'type' in value:
            value['widget_type'] = value.pop('type')
        return {KEY_ZDISPLAY: {'event': 'selection', **value}}

    def _expand_zrange(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zRange to read_range event with defaults."""
        if 'min' not in value:
            value['min'] = 0
        if 'max' not in value:
            value['max'] = 100
        if 'step' not in value:
            value['step'] = 1
        if 'prompt' not in value:
            value['prompt'] = ''
        if 'disabled' not in value:
            value['disabled'] = False
        return {KEY_ZDISPLAY: {'event': 'read_range', **value}}

    def _expand_zterminal(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zTerminal to zTerminal event."""
        return {KEY_ZDISPLAY: {'event': 'zTerminal', **value}}

    def _expand_zprogress(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zProgress to progress_bar event.

        Shorthand for the longhand SSOT (`zDisplay: {event: progress_bar, ...}` →
        ProgressEvents.progress_bar). Defaults (label, show_percentage, …) live on
        the handler, so the shorthand only stamps the event name. One declaration
        renders a single frame (a state snapshot); animating it is the imperative
        progress_bar()/progress_iterator() loop.
        """
        return {KEY_ZDISPLAY: {'event': 'progress_bar', **value}}

    def _expand_zcrumbs(self, value: Any) -> Optional[Dict[str, Any]]:
        """Expand zCrumbs to zCrumbs event (fixes zCrumbs bug for Bifrost).

        SSOT default — `show: session` (the dynamic, 1:1-with-session trail) is the
        zero-config freebie, so the author shorthand collapses to it:
          • `zCrumbs: true`  → non-dict truthy → {show: session}
          • `zCrumbs:` / {}  → dict with no `show` → {show: session}
          • `zCrumbs: {show: manual|structure, …}` → opt into the other modes
            (structure takes an optional `parent` path; the old `show: static` is
            folded into structure — a parent is just a declared structural trail)
        Anything else (falsy / unknown show) still skips, exactly as before.
        """
        # Non-dict shorthand (`zCrumbs: true`) → dynamic session banner with defaults.
        if not isinstance(value, dict):
            if value is True:
                value = {'show': 'session'}
            else:
                self.logger.framework.debug(f"[ShorthandExpander] zCrumbs non-dict value {value!r}, skipping")
                return None
        elif 'show' not in value:
            # Bare/empty dict defaults to the session trail rather than rendering nothing.
            value = {**value, 'show': 'session'}

        show_value = value.get('show', False)
        valid_show_values = ('session', 'manual', 'structure', True)
        is_valid = (
            show_value in valid_show_values or
            (isinstance(show_value, str) and show_value.lower() in ('true', 'session', 'manual', 'structure'))
        )

        if is_valid:
            self.logger.framework.debug(f"[ShorthandExpander] Expanding zCrumbs with show={show_value}")
            # SESSION trail is NOT slimmed here. This expander can run at the dispatch
            # seam — for a deeply-nested chunk that fires BEFORE the full visit trail
            # has settled, so slimming here produced a partial trail (the leaf showed
            # only its own scope while a tiny page showed the whole chain). The live
            # session page-chain is now resolved at a SINGLE seam — the Bifrost
            # serializer (MessageUtils), the last point before the wire where
            # session['zCrumbs'] is final and complete (SSOT). We only normalize the
            # shorthand to {show: session} here and leave 'crumbs' for that seam to
            # fill. zCLI is unaffected: zCrumbs() reads session['zCrumbs'] live and
            # ignores the Bifrost-only 'crumbs' payload entirely.
            return {KEY_ZDISPLAY: {'event': 'zCrumbs', 'header': 'zCrumbs:', **value}}
        else:
            self.logger.framework.debug(f"[ShorthandExpander] zCrumbs show={show_value}, skipping")
            return None

    def _expand_zicon(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zIcon to icon event."""
        return {KEY_ZDISPLAY: {'event': 'icon', **value}}

    # ── Signal expanders ─────────────────────────────────────────────────────

    def _expand_zsignal(self, value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Expand zSignal longhand to the appropriate signal event.

        Reads the required `type` field (error|warning|success|info) and routes
        to the matching event string, stripping `type` before forwarding so the
        downstream handler only receives `content` (+ optional `indent`).

        Example:
            zSignal:
                type: success
                content: Record saved.
        """
        signal_type = value.get('type')
        # The four status verdicts + two non-status brand emphasis tones.
        valid_types = ('error', 'warning', 'success', 'info', 'primary', 'secondary')
        if signal_type not in valid_types:
            if self.logger:
                self.logger.framework.debug(
                    f"[ShorthandExpander] zSignal missing/invalid type '{signal_type}', skipping"
                )
            return None
        params = {k: v for k, v in value.items() if k != 'type'}
        return {KEY_ZDISPLAY: {'event': signal_type, **params}}

    def _expand_zerror(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zError to error signal event."""
        return {KEY_ZDISPLAY: {'event': 'error', **value}}

    def _expand_zwarning(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zWarning to warning signal event."""
        return {KEY_ZDISPLAY: {'event': 'warning', **value}}

    def _expand_zsuccess(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zSuccess to success signal event."""
        return {KEY_ZDISPLAY: {'event': 'success', **value}}

    def _expand_zinfo(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zInfo to info signal event."""
        return {KEY_ZDISPLAY: {'event': 'info', **value}}

    def _expand_zprimary(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zPrimary to primary emphasis signal event (non-status)."""
        return {KEY_ZDISPLAY: {'event': 'primary', **value}}

    def _expand_zsecondary(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Expand zSecondary to secondary emphasis signal event (non-status)."""
        return {KEY_ZDISPLAY: {'event': 'secondary', **value}}
