# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_paths.py
"""
zPath resolution helpers for the file transfer adapter.

Thin wrappers over the zPath SSOT (``zOS.zPath``): the dotted ``@.`` / ``~.`` /
bare rule lives in the leaf, so zImport / zExport agree with every other
subsystem on how dot-notation maps onto the OS filesystem. This module only
adds the transfer-specific concern of splitting a trailing *filename* off a
dotted source path.
"""

import os as _os
from typing import Any

from zOS.zPath import resolve_base, resolve_dotted
from zOS.zVocabulary import PATH_SYMBOL_AT, PATH_SYMBOL_TILDE, PATH_SEP_DOT

# Last segment is treated as a filename extension (not a dir separator)
# when it matches a known suffix.
FILE_EXTENSIONS = {"csv", "json", "tsv", "txt", "xlsx", "xml", "yaml", "yml"}

_AT_DOT = PATH_SYMBOL_AT + PATH_SEP_DOT       # "@."
_TILDE_DOT = PATH_SYMBOL_TILDE + PATH_SEP_DOT  # "~."


def resolve_file_path(zos: Any, source: str) -> str:
    """
    Resolve zPath dot-notation to an OS file path.

      @.Data.imports.contacts_import.csv  →  {zSpace}/Data/imports/contacts_import.csv
      ~.tmp.import.csv                    →  {home}/tmp/import.csv
      Data.imports.foo.csv               →  {zSpace}/Data/imports/foo.csv

    A literal OS path (contains a real separator) is returned unchanged so
    callers can hand zTransfer an absolute path directly (e.g. an upload temp).

    The base dir is resolved by zOS.zPath (SSOT); the trailing filename split
    (extension-aware) is transfer-specific and stays here.
    """
    path = str(source).strip()

    # Literal filesystem path — pass through untouched.
    if _os.sep in path and not path.startswith((_AT_DOT, _TILDE_DOT)):
        return path

    zspace = zos.session.get("zSpace", _os.getcwd())

    if path.startswith(_AT_DOT):
        symbol, segments = PATH_SYMBOL_AT, path[len(_AT_DOT):].split(PATH_SEP_DOT)
    elif path.startswith(_TILDE_DOT):
        symbol, segments = PATH_SYMBOL_TILDE, path[len(_TILDE_DOT):].split(PATH_SEP_DOT)
    else:
        symbol, segments = None, path.split(PATH_SEP_DOT)

    if len(segments) >= 2 and segments[-1].lower() in FILE_EXTENSIONS:
        filename = f"{segments[-2]}.{segments[-1]}"
        dir_segments = segments[:-2]
    else:
        filename = segments[-1]
        dir_segments = segments[:-1]

    # Base join via the SSOT primitive (parts[0] is the symbol token for @/~).
    full = [symbol, *dir_segments] if symbol else dir_segments
    base = resolve_base(symbol, full, zspace)
    return _os.path.join(base, filename)


def resolve_output_dir(zos: Any, output: str) -> str:
    """
    Resolve zPath dot-notation for a directory target.

      @.Data.exports  →  {zSpace}/Data/exports
      ~.tmp.out       →  {home}/tmp/out
      Data.exports    →  {zSpace}/Data/exports
    """
    zspace = zos.session.get("zSpace", _os.getcwd())
    return resolve_dotted(output, zspace)
