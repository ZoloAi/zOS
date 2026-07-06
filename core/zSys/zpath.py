# zOS/core/zSys/zpath.py

"""
zPath grammar — the SSOT leaf for zPath string ↔ parts decomposition.

zOS addresses everything by zPath (``@.zViews.zProducts.zUI.zOS.zOS``,
``~.zMachine.Config``, ``&.myplugin``, ``$zAbout``). Historically every
subsystem re-parsed that grammar by hand — ``s[2:]``, ``s.lstrip('@.')``,
``s.split('.')`` — scattered across routing, navigation, dispatch, display and
zGuard. A folder rename (``UI`` → ``zViews``) silently broke a dozen of those
ad-hoc copies because the grammar lived nowhere and everywhere.

This module is that ONE place. It is intentionally a Layer-0 leaf:

* **Pure** — no ``zos``, no router, no filesystem, no config. It only knows the
  *shape* of a zPath string, never how to resolve one.
* **Format-agnostic** — it operates on the already-parsed string value, so
  ``.zolo`` / ``.yaml`` / ``.json`` origin is irrelevant (string-first).
* **Dependency-free** — every layer (zParser L2, zNavigation L2, zServer L4,
  zGuard) can import it with zero circular/layer tension. That freedom is the
  whole reason the duplicate copies existed; remove the friction, remove the
  copies.

Consumers add their own *context* on top of these parts:

* ``zParser.resolve_data_path``     parts → filesystem path   (adds zSpace root)
* ``ZLinkResolver.resolve_href_to_route``  parts → URL        (adds the route map)

The grammar
-----------
A zPath is an optional leading **sigil** followed by dot-delimited **segments**::

    @.zViews.zProducts.zUI.zOS.zOS
    │ └────────── segments ──────┘
    sigil

Sigils (filesystem/addressable):
    ``@`` workspace-relative · ``~`` home (``~.zMachine`` = machine store) ·
    ``&`` plugins

Navigation hrefs additionally use:
    ``$`` intra-app delta · ``#`` anchor/placeholder · ``http(s)://`` external

Navigation convention: a page href ends in ``…zUI.<File>.<Block>``; the **block**
is the last segment and the **file stem** is the segment before it (the ``zUI.``
marker precedes the stem). One file = one URL; the block is intra-page nav.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from zOS.zVocabulary import ZPATH_REFERENCE_KEYS

# ── Sigils (the grammar SSOT — other modules' SYMBOL_* may re-point here) ──────
SIGIL_WORKSPACE = "@"
SIGIL_HOME = "~"
SIGIL_PLUGIN = "&"
SIGIL_DELTA = "$"

# Filesystem/addressable sigils — a string starting with one of these is a zPath.
PATH_SIGILS: Tuple[str, ...] = (SIGIL_WORKSPACE, SIGIL_HOME, SIGIL_PLUGIN)

# ── Classification kinds (the full href/zPath taxonomy) ───────────────────────
KIND_NAV = "nav"                  # @.<views_folder>.… → page navigation (→ URL)
KIND_BACKEND = "backend"          # @.models.… / .zSchema.… → data, never a URL
KIND_ASSET = "asset"              # @./~./&. filesystem resource (image, file, …)
KIND_DELTA = "delta"              # $X intra-app navigation
KIND_EXTERNAL = "external"        # http(s)://…
KIND_ANCHOR = "anchor"            # #section
KIND_PLACEHOLDER = "placeholder"  # '' or bare '#'
KIND_PLAIN = "plain"             # not a recognized sigil (bare token)

# Markers used by the backend heuristic (data references, never navigable URLs).
_BACKEND_HEAD = "models"
_BACKEND_MARKER = "zSchema"


@dataclass(frozen=True)
class ZPathParts:
    """Decomposed zPath: leading sigil + sigil-stripped, dot-split segments.

    ``file``/``block`` encode the navigation convention (``…<File>.<Block>``);
    they are only meaningful for navigation hrefs but are cheap accessors over
    the same segment list, so callers pick what they need.
    """

    symbol: str
    segments: Tuple[str, ...]
    raw: str

    @property
    def body(self) -> str:
        """The sigil-stripped path body, dot-joined (no leading dot)."""
        return ".".join(self.segments)

    @property
    def block(self) -> str:
        """Trailing segment — the navigation block (last ``.`` component)."""
        return self.segments[-1] if self.segments else ""

    @property
    def file(self) -> str:
        """Segment before the block — the navigation file stem.

        Falls back to the only segment when the path has just one component.
        """
        if len(self.segments) >= 2:
            return self.segments[-2]
        return self.segments[-1] if self.segments else ""

    @property
    def folder(self) -> Tuple[str, ...]:
        """Directory segments before the ``<File>.<Block>`` tail.

        Navigation hrefs are written ``@.<dir…>.zUI.<File>.<Block>``; this drops
        the trailing ``zUI`` grammar marker so the result is the real folder path
        (e.g. ``('zViews','zStack','zCloud')``). Empty for paths with < 3
        meaningful segments. Lets the reverse router disambiguate two same-named
        files that live in different folders (smart routing is one file = one URL,
        but "file" must include its directory, not just the basename).
        """
        head = self.segments[:-2]
        if head and head[-1] == "zUI":
            head = head[:-1]
        return head

    @property
    def is_zpath(self) -> bool:
        return self.symbol in PATH_SIGILS


def is_zpath(value: object) -> bool:
    """True when ``value`` is a string beginning with a path sigil (``@ ~ &``)."""
    return isinstance(value, str) and value[:1] in PATH_SIGILS


def is_reference_key(key: object) -> bool:
    """True if ``key`` is a property that *accepts* a zPath value (SSOT gate).

    zPath resolution is EVENT-SCOPED: a string is only treated as a zPath when
    its parent key is a declared reference-bearing property (``href``, ``src``,
    ``model``, ``zLink``, ``zVaFolder`` …). Every other key is string-first, so a
    literal like ``suffix: @company.com`` is emitted verbatim. The canonical key
    set lives in ``zVocabulary.ZPATH_REFERENCE_KEYS`` — one contract for zOS and
    zGuard. New events that accept a zPath declare their key there.
    """
    return key in ZPATH_REFERENCE_KEYS


def split(value: str) -> ZPathParts:
    """Decompose a zPath string into ``(symbol, segments, raw)``.

    The dumb, canonical replacement for hand-rolled ``s[2:]`` / ``s.lstrip('@.')``
    / ``s.split('.')``. A leading sigil is peeled; the remainder is trimmed of
    its boundary dots and split on ``.``. Non-zPath input yields an empty symbol
    and the whole string as a single-segment body.

    Examples::

        split("@.zViews.zUI.Login.Login")
        # ZPathParts(symbol='@', segments=('zViews','zUI','Login','Login'))
        split("~.zMachine.Config")
        # ZPathParts(symbol='~', segments=('zMachine','Config'))
    """
    raw = value if isinstance(value, str) else ""
    symbol = raw[:1] if raw[:1] in PATH_SIGILS else ""
    body = raw[1:] if symbol else raw
    body = body.strip(".")
    segments = tuple(p for p in body.split(".") if p) if body else ()
    return ZPathParts(symbol=symbol, segments=segments, raw=raw)


def strip_symbol(value: str) -> str:
    """Return the zPath body with the leading sigil and boundary dots removed.

    Replacement for ``s[2:]`` / ``s.lstrip('@.')``-style prefix surgery.
    """
    return split(value).body


def nav_pair(value: str) -> Optional[Tuple[str, str]]:
    """Return ``(file_stem, block)`` for a navigation href, or ``None``.

    This is the canonical input to ``router.reverse_route`` (one file = one URL;
    reverse_route normalizes any ``zUI.`` prefix itself). Returns ``None`` for
    paths with fewer than two segments (single-segment data/folder references
    have no ``(file, block)`` pair).
    """
    triple = nav_triple(value)
    return (triple[1], triple[2]) if triple else None


def nav_triple(value: str) -> Optional[Tuple[Tuple[str, ...], str, str]]:
    """Return ``(folder, file_stem, block)`` for a navigation href, or ``None``.

    Directory-aware superset of :func:`nav_pair`: ``folder`` carries the segments
    before the ``<File>.<Block>`` tail (the ``zUI`` marker stripped), so the
    reverse router can disambiguate two same-named files in different folders.
    ``None`` for paths with fewer than two segments (no ``(file, block)`` pair).
    """
    parts = split(value)
    if len(parts.segments) >= 2:
        return parts.folder, parts.file, parts.block
    return None


def join(symbol: str, *parts: str) -> str:
    """Rebuild a zPath from a sigil and segment fragments (inverse of ``split``).

    Each fragment may itself be dotted (e.g. a folder ``@.a.b`` and a file
    ``zUI.X``); fragments are flattened and re-joined. ``symbol`` may be a bare
    sigil (``'@'``) or empty.
    """
    sigil = symbol if symbol in PATH_SIGILS else ""
    segs = []
    for frag in parts:
        if not frag:
            continue
        # Allow callers to pass already-sigiled fragments (e.g. '@.a').
        frag_parts = split(frag).segments if frag[:1] in PATH_SIGILS else tuple(
            p for p in frag.strip(".").split(".") if p
        )
        segs.extend(frag_parts)
    body = ".".join(segs)
    if sigil:
        return f"{sigil}.{body}" if body else sigil
    return body


def classify(value: object, views_folder: Optional[str] = None) -> str:
    """Classify a zPath / href string into one of the ``KIND_*`` roles.

    The single SSOT for "what *is* this string?" — replacing prefix-sniffing
    scattered across display, navigation and zGuard message utils.

    ``views_folder`` (the zServer ``FOLDER_UI`` constant) is required to
    distinguish navigable pages (``@.<views_folder>.…`` → ``KIND_NAV``) from
    generic filesystem assets (``KIND_ASSET``). When omitted, every ``@``/``~``/
    ``&`` path that is not a backend reference is reported as ``KIND_ASSET`` —
    callers that only need the coarse href taxonomy (delta/zpath/external/
    anchor) do not pass it.
    """
    if not isinstance(value, str) or not value or value == "#":
        return KIND_PLACEHOLDER
    if value.startswith(("http://", "https://")):
        return KIND_EXTERNAL
    if value.startswith(SIGIL_DELTA):
        return KIND_DELTA
    if value.startswith("#"):
        return KIND_ANCHOR
    if value[:1] not in PATH_SIGILS:
        return KIND_PLAIN

    parts = split(value)
    if parts.segments and (parts.segments[0] == _BACKEND_HEAD or _BACKEND_MARKER in parts.segments):
        return KIND_BACKEND
    if (
        views_folder
        and parts.symbol == SIGIL_WORKSPACE
        and parts.segments
        and parts.segments[0] == views_folder
    ):
        return KIND_NAV
    return KIND_ASSET


# ── Golden self-check (run: python -m zSys.zpath) ─────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    FU = "zViews"
    ok = True

    # Path cases — assert full decomposition (split + nav_pair + classify).
    path_cases = [
        ("@.zViews.zProducts.zUI.zOS.zOS", "@",
         ("zViews", "zProducts", "zUI", "zOS", "zOS"), ("zOS", "zOS"), KIND_NAV),
        ("@.zViews.zUI.Login.Login", "@",
         ("zViews", "zUI", "Login", "Login"), ("Login", "Login"), KIND_NAV),
        ("@.zViews.zProducts.zOS.Concepts.zUI.zServer_Hub.zServer_Hub", "@",
         ("zViews", "zProducts", "zOS", "Concepts", "zUI", "zServer_Hub", "zServer_Hub"),
         ("zServer_Hub", "zServer_Hub"), KIND_NAV),
        ("@.models.zSchema.zApps", "@",
         ("models", "zSchema", "zApps"), ("zSchema", "zApps"), KIND_BACKEND),
        ("@.Data", "@", ("Data",), None, KIND_ASSET),
        ("~.zMachine.Config", "~", ("zMachine", "Config"), ("zMachine", "Config"), KIND_ASSET),
        ("&.myplugin", "&", ("myplugin",), None, KIND_ASSET),
        # Relative (sigil-less) zPath still decomposes — used by route fetch helpers.
        ("zUI.index.zVaF", "", ("zUI", "index", "zVaF"), ("index", "zVaF"), KIND_PLAIN),
    ]
    for raw, sym, segs, npair, kind in path_cases:
        p = split(raw)
        if not (p.symbol == sym and p.segments == segs
                and nav_pair(raw) == npair and classify(raw, FU) == kind):
            ok = False
            print(f"FAIL path {raw!r}: symbol={p.symbol!r} segs={p.segments} "
                  f"pair={nav_pair(raw)} kind={classify(raw, FU)}")

    # Href tokens — only the taxonomy matters (never passed to split()).
    href_cases = [
        ("$zAbout", KIND_DELTA),
        ("https://zolo.io", KIND_EXTERNAL),
        ("#features", KIND_ANCHOR),
        ("#", KIND_PLACEHOLDER),
        ("", KIND_PLACEHOLDER),
    ]
    for raw, kind in href_cases:
        if classify(raw, FU) != kind:
            ok = False
            print(f"FAIL href {raw!r}: kind={classify(raw, FU)} (want {kind})")

    # join / strip round-trips.
    assert join("@", "zViews", "zUI.Login", "Login") == "@.zViews.zUI.Login.Login"
    assert join("@", "@.zViews", "zUI.X") == "@.zViews.zUI.X"
    assert strip_symbol("@.zViews.zUI.X") == "zViews.zUI.X"
    print("zpath golden:", "PASS" if ok else "FAIL")
