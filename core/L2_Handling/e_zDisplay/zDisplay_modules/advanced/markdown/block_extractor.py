"""
Block Extractor - Parses markdown into block-level structures.

Extracts:
- Code blocks (```)
- Headings (# through ######)
- Blockquotes (>)
- Lists (bullet and numbered)
- Paragraphs

Author: zOS Framework
Version: 3.0.0
"""

from zOS import re


# ── List marker grammar — SSOT shared in spirit with zLSP str_hint and the
#    zBifrost text_renderer. The MARKER is the type (authored explicitly):
#      Unordered:  -  *  +                  → disc / circle / square
#      Ordered:    1-  a-  A-  i-  I-        → decimal / alpha / roman
#    Ordered token = digits | single letter | roman string, space-guarded so
#    'well- known' / '5-minute' stay prose. A list LEVEL's style is set by the
#    first item's marker at that depth.
_OL_TOKEN = r'(?:\d+|[ivxlcdmIVXLCDM]+|[A-Za-z])'
_RE_UL_ITEM = re.compile(r'^([-*+])[ \t]+(.*)$')
_RE_OL_ITEM = re.compile(r'^(' + _OL_TOKEN + r')-[ \t]+(.*)$')
_RE_LIST_ITEM = re.compile(r'^(?:[-*+]|' + _OL_TOKEN + r'-)[ \t]+')
_RE_EMPTY_MARK = re.compile(r'^[-*+][ \t]*$')


def _marker_style(stripped: str):
    """Map a list line's marker to its canonical style, or None if not a list line."""
    m = _RE_UL_ITEM.match(stripped)
    if m:
        return {'-': 'disc', '*': 'circle', '+': 'square'}[m.group(1)]
    m = _RE_OL_ITEM.match(stripped)
    if m:
        tok = m.group(1)
        if tok.isdigit():
            return 'number'
        if tok in ('i', 'I') or (len(tok) > 1 and all(ch in 'ivxlcdm' for ch in tok.lower())):
            return 'upper-roman' if tok.isupper() else 'roman'
        return 'upper-letter' if tok.isupper() else 'letter'
    return None


class BlockExtractor:
    """Extracts block-level markdown structures."""

    def extract_blocks(self, content: str) -> list:
        """
        Split content into blocks.
        
        Handles semantic multiline:
        - \x1F (Unit Separator) = line break within paragraph
        - \n = paragraph break
        
        Args:
            content: Full markdown content
            
        Returns:
            List of tuples: (block_type, block_content)
            block_type: 'code', 'heading', 'blockquote', 'list', 'paragraph'
        """
        if not content or not content.strip():
            return []

        # Protect fenced code blocks from the \n doubling below.
        # Without this, a blank line inside a code block (\n\n) becomes \n\n\n\n
        # (three blank lines) after the global replace — visible as extra empty
        # lines in the zCLI code block renderer.
        _fenced: list = []

        def _fence_protect(m: re.Match) -> str:
            _fenced.append(m.group(0))
            return f'\x03FENCE{len(_fenced) - 1}\x03'

        content = re.sub(r'```[\w]*\n[\s\S]*?```', _fence_protect, content)

        # Process semantic distinction
        content = content.replace('\n', '\n\n')  # Explicit \n → paragraph break
        content = content.replace('\x1F', '\n')  # Unit separator → line break

        # Restore fenced code blocks with their original internal newlines intact
        for i, block in enumerate(_fenced):
            content = content.replace(f'\x03FENCE{i}\x03', block)

        blocks = []
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                i += 1
                continue

            # Code block
            if stripped.startswith('```'):
                code_block, lines_consumed = self._extract_code_block(lines, i)
                if code_block:
                    blocks.append(('code', code_block))
                    i += lines_consumed
                    continue

            # Heading
            heading_match = re.match(r'^(#{1,6})\s*(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                blocks.append(('heading', (level, text)))
                i += 1
                continue

            # Blockquote
            if stripped.startswith('>'):
                quote_block, lines_consumed = self._extract_blockquote(lines, i)
                blocks.append(('blockquote', quote_block))
                i += lines_consumed
                continue

            # List (regular item, numbered/alpha/roman item, or empty nesting marker)
            if _RE_LIST_ITEM.match(stripped) or _RE_EMPTY_MARK.match(stripped):
                list_block, lines_consumed = self._extract_list(lines, i)
                blocks.append(('list', list_block))
                i += lines_consumed
                continue

            # Paragraph
            para_block, lines_consumed = self._extract_paragraph(lines, i)
            blocks.append(('paragraph', para_block))
            i += lines_consumed

        return blocks

    def _extract_code_block(self, lines: list, start_idx: int) -> tuple:
        """
        Extract code block starting with ```.
        
        Returns:
            ((language, code_content), lines_consumed) or (None, 0)
        """
        if not lines[start_idx].strip().startswith('```'):
            return None, 0

        first_line = lines[start_idx].strip()
        language = first_line[3:].strip() if len(first_line) > 3 else ''

        code_lines = []
        i = start_idx + 1

        while i < len(lines):
            if lines[i].strip().startswith('```'):
                code_content = '\n'.join(code_lines)
                return (language, code_content), i - start_idx + 1
            code_lines.append(lines[i])
            i += 1

        # No closing marker - treat as regular text
        return None, 0

    def _extract_list(self, lines: list, start_idx: int) -> tuple:
        """
        Extract consecutive list items.

        Recognises three forms of list line:
        - Regular item:   ``- text`` / ``* text`` / ``1. text``
        - Empty marker:   ``-`` or ``- `` (dash alone, used as nesting container
                          — matches zUL/zOL's empty-item nesting convention)
        - Blank line:     collected and skipped (allows blank lines between items)

        Returns:
            (list_content, lines_consumed)
        """
        list_lines = []
        i = start_idx

        while i < len(lines):
            stripped = lines[i].strip()

            # Blank line within list — keep so items stay in one block
            if not stripped:
                list_lines.append(lines[i])
                i += 1
                continue

            # Regular list item:  - * + text  /  1- a- A- i- I- text
            if _RE_LIST_ITEM.match(stripped):
                list_lines.append(lines[i])
                i += 1
                continue

            # Empty nesting marker:  - / * / +  (alone)
            if _RE_EMPTY_MARK.match(stripped):
                list_lines.append(lines[i])
                i += 1
                continue

            break

        return '\n'.join(list_lines), i - start_idx

    def _extract_blockquote(self, lines: list, start_idx: int) -> tuple:
        """
        Extract consecutive blockquote lines.
        
        Returns:
            (quote_content, lines_consumed)
        """
        quote_lines = []
        i = start_idx

        while i < len(lines):
            stripped = lines[i].strip()

            # Empty line - check if quote continues
            if not stripped:
                if i + 1 < len(lines) and lines[i + 1].strip().startswith('>'):
                    quote_lines.append(lines[i])
                    i += 1
                    continue
                else:
                    break

            # Blockquote line
            if stripped.startswith('>'):
                quote_lines.append(lines[i])
                i += 1
            else:
                break

        return '\n'.join(quote_lines), i - start_idx

    def _extract_paragraph(self, lines: list, start_idx: int) -> tuple:
        """
        Extract paragraph block.
        
        Returns:
            (paragraph_content, lines_consumed)
        """
        para_lines = []
        i = start_idx

        while i < len(lines):
            stripped = lines[i].strip()

            # End conditions
            if not stripped:
                break
            if stripped.startswith('```'):
                break
            if _RE_LIST_ITEM.match(stripped) or _RE_EMPTY_MARK.match(stripped):
                break

            para_lines.append(lines[i])
            i += 1

        return '\n'.join(para_lines), i - start_idx

    def extract_list_items(self, content: str) -> list:
        """
        Extract list items, preserving nesting as nested arrays.

        Indented items (leading spaces before the list marker) become sublists
        attached to the previous parent item — matching the nested-array contract
        of display.list():

            ["Parent", ["Child A", "Child B"], "Parent two", ["Child C"]]

        This relies on leading whitespace being preserved in the raw list block
        (str_hint.py keeps relative indentation for zMD continuation lines).

        Args:
            content: Markdown list block content (may contain indented child items)

        Returns:
            Potentially-nested list of item strings / sub-lists
        """
        root: list = []
        prev_indent: int = -1
        # Stack entries: (indent_of_first_item_at_this_level, list_ref)
        stack: list = [(-1, root)]

        for line in content.split('\n'):
            if not line.strip():
                continue

            stripped = line.strip()
            indent = len(line) - len(stripped)

            # Empty nesting marker (-, *, + alone) — skip content-wise but keep
            # prev_indent unchanged so the next deeper item nests naturally.
            if _RE_EMPTY_MARK.match(stripped):
                continue

            # Bullet (- * +) or ordered (1- a- A- i- I-) item — capture the text.
            match = _RE_UL_ITEM.match(stripped)
            if match:
                text = match.group(2).rstrip()
            else:
                match = _RE_OL_ITEM.match(stripped)
                if not match:
                    continue
                text = match.group(2).rstrip()

            if indent > prev_indent and prev_indent >= 0:
                # Deeper indent → nest under previous item in current list
                parent_list = stack[-1][1]
                if parent_list:
                    nested: list = []
                    parent_list.append(nested)
                    stack.append((indent, nested))
                    nested.append(text)
                else:
                    # No prior item at this level — add directly
                    parent_list.append(text)
            elif indent < prev_indent:
                # Shallower indent → pop stack until we match or exceed this indent
                while len(stack) > 1 and indent < stack[-1][0]:
                    stack.pop()
                stack[-1][1].append(text)
            else:
                # Same level as last item
                stack[-1][1].append(text)

            prev_indent = indent

        return root

    def detect_list_style(self, content: str) -> str:
        """
        Detect if list is bullet or numbered (legacy single-style probe).

        Returns:
            'bullet' or 'number'
        """
        first_line = content.strip().split('\n')[0].strip()
        style = _marker_style(first_line)
        return 'number' if style in ('number', 'letter', 'upper-letter', 'roman', 'upper-roman') else 'bullet'

    def detect_list_styles(self, content: str) -> list:
        """
        Resolve the canonical style for each nesting DEPTH from the actual markers.

        The marker is the type (1- a- A- i- I- / - * +). A level's style is set by
        the FIRST item seen at that indent; depths are ordered by increasing indent.
        Returns a per-depth list suitable for display.list(style=[...]) cascading.

            "1- a\n    - b\n        * c"  →  ['number', 'disc', 'circle']
        """
        seen: dict = {}
        for line in content.split('\n'):
            if not line.strip():
                continue
            stripped = line.strip()
            style = _marker_style(stripped)
            if style is None:
                continue
            indent = len(line) - len(line.lstrip())
            seen.setdefault(indent, style)
        if not seen:
            return ['disc']
        return [seen[k] for k in sorted(seen)]

    def extract_styled_list(self, content: str) -> dict:
        """
        Parse a list block into a STYLED tree — every sublist carries its own
        style (from its first item's marker), so different branches at the same
        depth can use different markers (e.g. an `a-` sublist next to a `-` one).
        This is the SSOT counterpart to the zBifrost per-node renderer.

        Returns:
            {'_style': <style>, '_items': [ {'text': str, '_children': node|None}, ... ]}
        """
        root = {'_style': None, '_items': []}
        stack = [{'node': root, 'indent': -1}]

        for line in content.split('\n'):
            if not line.strip():
                continue
            stripped = line.strip()
            if _RE_EMPTY_MARK.match(stripped):
                continue
            style = _marker_style(stripped)
            if style is None:
                continue
            m = _RE_UL_ITEM.match(stripped) or _RE_OL_ITEM.match(stripped)
            text = m.group(2).rstrip()
            indent = len(line) - len(line.lstrip())

            top = stack[-1]
            if top['indent'] < 0:
                top['indent'] = indent
                top['node']['_style'] = style
            elif indent > top['indent']:
                items = top['node']['_items']
                if items:
                    last = items[-1]
                    if last['_children'] is None:
                        last['_children'] = {'_style': style, '_items': []}
                    stack.append({'node': last['_children'], 'indent': indent})
                    top = stack[-1]
            elif indent < top['indent']:
                while len(stack) > 1 and indent < stack[-1]['indent']:
                    stack.pop()
                top = stack[-1]

            top['node']['_items'].append({'text': text, '_children': None})

        if root['_style'] is None:
            root['_style'] = 'disc'
        return root
