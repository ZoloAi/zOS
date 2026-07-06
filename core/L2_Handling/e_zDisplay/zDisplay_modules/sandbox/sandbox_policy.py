# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/sandbox/sandbox_policy.py

"""
zTerminal sandbox policy — Single Source of Truth
=================================================

The restricted ``__builtins__`` mapping and the import allow-list that gate
``zTerminal`` Python execution. BOTH execution surfaces import from here so the
policy can never drift between them:

  - zCLI    → ``terminal_executor._execute_python`` (local, this repo)
  - Bifrost → zGuard ``bridge_event_client.execute_code`` (sealed WS path)

Honest scope — a fence, not a vault
-----------------------------------
This limits what a *casual* snippet can do; it is **not** a hard wall against
hostile code. The live instance is exposed to snippets as ``z`` (full framework
reach), and object-graph traversal can in principle reach internals. The real
boundary is the fail-closed ``ZTERMINAL_MODE`` opt-in gate in
``terminal_executor`` — never enable ``sandbox`` / ``trust`` for ``.zolo``
content you did not write or do not trust.

What the allow-list does guarantee
----------------------------------
Only **pure, side-effect-free** modules can be imported: maths, data, and the
framework namespace. Nothing here can touch the filesystem, network, or
processes — there is no ``os``, ``sys``, ``io``, ``open``, ``subprocess``,
``socket``, or ``importlib``. Identical on local and web surfaces.
"""

import builtins

# Pure-computation stdlib + the framework namespace. Anything that can reach the
# machine (os/sys/io/open/subprocess/socket/importlib/...) is deliberately absent.
SANDBOX_ALLOWED_IMPORTS = frozenset({
    "zOS", "math", "random", "datetime", "json", "re",
    "collections", "itertools", "functools",
})


def make_safe_import(allowed=SANDBOX_ALLOWED_IMPORTS):
    """Return an ``__import__`` replacement that permits only ``allowed`` modules.

    Submodule roots are checked (``datetime.timezone`` → root ``datetime``), so a
    whitelisted package's submodules import while everything else fails closed
    with a clear ``ImportError``.
    """
    real_import = builtins.__import__

    def safe_import(name, globs=None, locs=None, fromlist=(), level=0):
        root = (name or "").split(".", 1)[0]
        if root not in allowed:
            allowed_str = ", ".join(sorted(allowed))
            raise ImportError(
                f"Import of '{name}' is not allowed in the zTerminal sandbox. "
                f"Allowed: {allowed_str}"
            )
        return real_import(name, globs, locs, fromlist, level)

    return safe_import


def build_safe_builtins(extra=None, allowed_imports=SANDBOX_ALLOWED_IMPORTS):
    """Build the restricted ``__builtins__`` mapping shared by both sandboxes.

    Args:
        extra: optional dict merged on top — for surface-specific entries such as
            an interactive ``input`` that routes to the terminal or a WebSocket.
        allowed_imports: import allow-list backing the controlled ``__import__``.

    Returns:
        A fresh dict suitable for ``exec(code, {"__builtins__": <this>}, {})``.
    """
    safe = {
        # Controlled import — only SANDBOX_ALLOWED_IMPORTS pass.
        "__import__": make_safe_import(allowed_imports),
        # Output
        "print": print,
        # Types & conversions
        "int": int, "float": float, "str": str, "bool": bool,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "bytes": bytes, "bytearray": bytearray,
        # Iteration & sequences
        "range": range, "enumerate": enumerate, "zip": zip,
        "map": map, "filter": filter, "reversed": reversed, "sorted": sorted,
        "len": len, "min": min, "max": max, "sum": sum,
        "all": all, "any": any,
        # Math
        "abs": abs, "round": round, "pow": pow, "divmod": divmod,
        # String
        "chr": chr, "ord": ord, "repr": repr, "format": format,
        # Object inspection (safe subset)
        "type": type, "isinstance": isinstance, "issubclass": issubclass,
        "hasattr": hasattr, "getattr": getattr,
        "callable": callable, "id": id, "hash": hash,
        # Exceptions (for try/except)
        "Exception": Exception, "TypeError": TypeError, "ValueError": ValueError,
        "KeyError": KeyError, "IndexError": IndexError,
        "AttributeError": AttributeError, "RuntimeError": RuntimeError,
        "StopIteration": StopIteration, "ZeroDivisionError": ZeroDivisionError,
        "ImportError": ImportError, "TimeoutError": TimeoutError,
        # Constants
        "True": True, "False": False, "None": None,
    }
    if extra:
        safe.update(extra)
    return safe


__all__ = ["SANDBOX_ALLOWED_IMPORTS", "make_safe_import", "build_safe_builtins"]
