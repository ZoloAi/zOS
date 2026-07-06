# zOS/core/zPath.py
"""
zPath — Root SSOT for zPath *resolution logic*.

Sibling to ``zVocabulary``: where ``zVocabulary`` owns the path *atoms*
(``@``, ``~``, ``.``, the ``zSpace`` key), this module owns the *behavior* of
turning a zPath into a real filesystem location. It is the single place that
answers "what does ``@.`` mean?" so the rule cannot drift across subsystems.

Design contract (do not break)
-------------------------------
- **Dependency-free leaf.** Imports ONLY the stdlib ``os`` and ``zVocabulary``.
  It must never import from ``zOS`` layers (L1-L4), so any layer can import it
  during boot without a circular import — the same guarantee ``zVocabulary``
  relies on.
- **Data lives in zVocabulary, logic lives here.** Symbols/keys come from
  ``zVocabulary``; functions never move into ``zVocabulary``.
- **Behavior-preserving home.** ``resolve_base`` mirrors the historical
  ``zParser.resolve_symbol_path`` semantics exactly so the canonical decoder can
  delegate to it without changing output.

Canonical grammar
-----------------
Every zPath is ``<symbol> . <dot-separated path>`` — the leading symbol is its
own dot-delimited token (``parts[0]``), exactly like ``zMachine.`` is. The dot
after ``@`` / ``~`` is the consistent "symbol ends, path begins" delimiter, not
redundant punctuation.

- ``@`` (at)      → relative to ``zSpace`` (the workspace / app root)
- ``~`` (tilde)   → relative to the user's HOME (``expanduser``)
- (no symbol)     → relative to ``zSpace``

``~`` and ``zMachine`` are SIBLING symbols, not parent/child: ``~`` is literal
home, while ``zMachine`` is the per-OS app-data dir (resolved by its own
upstream resolver via platformdirs — never spelled out as a ``~`` subpath).

Two-gate resolution contract (string-first safety)
--------------------------------------------------
A value is resolved as a zPath ONLY when BOTH gates pass:

1. **Event scope** — :func:`is_reference_key` — the key is a declared
   reference-bearing property (``ZPATH_REFERENCE_KEYS`` in ``zVocabulary``:
   ``href``/``src``/``model``/``zVaFolder``/``_navigate``/…). Arbitrary keys are
   never scanned for ``@``/``~``.
2. **Value shape** — :func:`is_zpath` — the value is dot-qualified (``@.``/``~.``).

This is why zOS does not contradict its own string-first law: ``suffix:
@company.com`` fails gate 1 (``suffix`` is not a reference key) AND gate 2 (no
dot after ``@``), so it is emitted verbatim. New events that accept a zPath
declare their key in ``ZPATH_REFERENCE_KEYS`` — nothing else resolves.

Entry points:
- ``resolve_base(symbol, parts, zspace)`` — low-level join primitive the dotted
  zVaFile decoder feeds pre-split path parts into.
- ``resolve_dotted(value, zspace)`` — DOTTED zPath string → path (``@.a.b`` /
  ``~.a.b`` / ``a.b``); literal OS paths pass through. Used by the dispatch /
  transfer layer.
- ``resolve_folder(value, zspace)`` — plain *folder* zPaths (mounts, serve_path,
  log dirs): one string → absolute path. Honors ``@.sub``, absolute, ``~`` home,
  bare-relative.
"""

import os

from zOS.zVocabulary import (
    PATH_SYMBOL_AT,
    PATH_SYMBOL_TILDE,
    PATH_SEP_DOT,
    ZPATH_REFERENCE_KEYS,
)

__all__ = ["is_zpath", "is_reference_key", "resolve_base", "resolve_dotted", "resolve_folder"]


def is_zpath(value) -> bool:
    """True if ``value`` is a DOT-QUALIFIED zPath (``@.…`` or ``~.…``).

    The leading symbol is its own token, so a real zPath always carries the
    ``@.`` / ``~.`` delimiter (the canonical grammar above). A bare ``@handle``,
    ``~user``, or ``user@host.com`` is NOT a zPath — it is a literal,
    string-first value and is returned verbatim by every consumer.

    This dot requirement is what keeps string-first fields (``prompt``,
    ``suffix``, ``label``, ``content`` …) from being mistaken for paths. It is a
    *value-shape* guard; the *event-scope* guard is :func:`is_reference_key`.
    """
    if not isinstance(value, str) or not value:
        return False
    at_dot = PATH_SYMBOL_AT + PATH_SEP_DOT       # "@."
    tilde_dot = PATH_SYMBOL_TILDE + PATH_SEP_DOT  # "~."
    return value.startswith(at_dot) or value.startswith(tilde_dot)


def is_reference_key(key) -> bool:
    """True if ``key`` is a property that *accepts* a zPath value (SSOT gate).

    zPath resolution is EVENT-SCOPED: only values sitting under a declared
    reference-bearing key (``href``, ``src``, ``model``, ``zVaFolder`` …) are
    ever path-resolved. Every other key is string-first and its value is passed
    through untouched — so ``suffix: @company.com`` stays literal.

    Resolvers MUST gate on this predicate before treating a value as a zPath;
    the canonical key set lives in ``zVocabulary.ZPATH_REFERENCE_KEYS`` so zOS
    and zGuard share one contract. New events declare their reference key there.
    """
    return key in ZPATH_REFERENCE_KEYS


def resolve_base(symbol, parts, zspace) -> str:
    """
    Join already-split path ``parts`` against the correct base for ``symbol``.

    Canonical zPath join (``parts[0]`` is the symbol token for ``@``/``~``):
        - ``@``  → ``os.path.join(zspace, *parts[1:])``       (workspace-relative)
        - ``~``  → ``os.path.join(<home>, *parts[1:])``       (home-relative)
        - else   → ``os.path.join(zspace, *parts)``           (workspace-relative)

    ``~`` means HOME (``expanduser('~')``) — a sibling of ``zMachine`` (the per-OS
    app-data dir, resolved upstream), not "absolute from root".

    Args:
        symbol: leading symbol (``PATH_SYMBOL_AT``, ``PATH_SYMBOL_TILDE``, or None)
        parts:  list of path components; for ``@``/``~`` ``parts[0]`` is the symbol
        zspace: workspace / app root

    Returns:
        str: the resolved base path (not normalized — caller may normalize)
    """
    parts = parts or []
    if symbol == PATH_SYMBOL_AT:
        return os.path.join(zspace, *parts[1:])
    if symbol == PATH_SYMBOL_TILDE:
        return os.path.join(os.path.expanduser(PATH_SYMBOL_TILDE), *parts[1:])
    return os.path.join(zspace, *parts)


def resolve_dotted(value, zspace) -> str:
    """
    Resolve a DOTTED zPath string to a path. Dots are the separators:

        @.Data.exports → {zspace}/Data/exports   (workspace-relative)
        ~.tmp.out      → {home}/tmp/out          (home-relative)
        Data.exports   → {zspace}/Data/exports   (bare = workspace-relative)

    A literal OS path (contains a real separator and no ``@.``/``~.`` prefix)
    passes through unchanged, so callers may hand an absolute path directly.

    Args:
        value:  the dotted zPath string (or falsy → ``zspace``)
        zspace: workspace / app root

    Returns:
        str: the resolved path (not normalized — caller may normalize)
    """
    if not value:
        return zspace

    v = str(value).strip()
    at_dot = PATH_SYMBOL_AT + PATH_SEP_DOT       # "@."
    tilde_dot = PATH_SYMBOL_TILDE + PATH_SEP_DOT  # "~."

    # Literal filesystem path — pass through untouched.
    if os.sep in v and not v.startswith((at_dot, tilde_dot)):
        return v

    if v.startswith(at_dot):
        symbol, rest = PATH_SYMBOL_AT, v[len(at_dot):]
    elif v.startswith(tilde_dot):
        symbol, rest = PATH_SYMBOL_TILDE, v[len(tilde_dot):]
    else:
        symbol, rest = None, v

    parts = rest.split(PATH_SEP_DOT) if rest else []
    full = [symbol, *parts] if symbol else parts
    return resolve_base(symbol, full, zspace)


def resolve_folder(value, zspace) -> str:
    """
    Resolve a plain *folder* zPath string to an absolute path.

    The one rule mounts / serve_path / log dirs share. Forgiving on input,
    canonical on output:
        - ``@.sub`` / ``@sub`` / ``@``  → under ``zspace``
        - absolute (``/srv/x``)          → as-is
        - ``~`` / ``~/sub``              → user home
        - bare relative (``sub``, ``.``) → under ``zspace``

    A stray leading ``/`` after ``@.`` is tolerated (``@./sub`` == ``@.sub``).

    Args:
        value:  the folder zPath string (or falsy → ``zspace``)
        zspace: workspace / app root

    Returns:
        str: absolute, normalized filesystem path
    """
    if not value:
        return os.path.normpath(zspace)

    v = str(value).strip()

    # Workspace-relative: @, @., @.sub
    if v.startswith(PATH_SYMBOL_AT):
        rest = v[len(PATH_SYMBOL_AT):].lstrip(PATH_SEP_DOT).lstrip("/")
        return os.path.normpath(os.path.join(zspace, rest)) if rest else os.path.normpath(zspace)

    # Home: ~, ~/sub  (legacy ~.sub tolerated → ~/sub)
    if v.startswith(PATH_SYMBOL_TILDE):
        tilde_dot = PATH_SYMBOL_TILDE + PATH_SEP_DOT
        if v.startswith(tilde_dot):
            v = PATH_SYMBOL_TILDE + "/" + v[len(tilde_dot):]
        return os.path.normpath(os.path.expanduser(v))

    # Absolute as-is
    if os.path.isabs(v):
        return os.path.normpath(v)

    # Bare relative ("sub", ".") → under workspace
    if v in (".", "./"):
        return os.path.normpath(zspace)
    return os.path.normpath(os.path.join(zspace, v))
