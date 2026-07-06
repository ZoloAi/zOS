# zLoader Plugin-Trust Gate Guide

> **Module:** `zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_trust.py`  
> **Purpose:** Single enforcement point deciding whether a plugin path is allowed to execute (zGuard seam).

---

## Why it exists

Loading a plugin runs arbitrary code:
- `.py` plugins are executed with `importlib.exec_module`
- `.js` plugins run via a Node subprocess (through zFunc)
- dotted **module import paths** (`pkg.mod.plugin`) execute the module's top-level
  code on `importlib.import_module`

…and the live `zos` instance is injected into them. `loader_trust` is the one place that gates this, so a security policy can decide *whether a given path may load* — without scattering checks across call sites.

---

## The seam (mirrors the zAuth shims)

```python
try:
    # Sealed enforcement when the zGuard wheel is installed
    from zguard.loader.plugin_trust import verify_plugin_trust
except ImportError:
    def verify_plugin_trust(_file_path, _zos=None, _logger=None) -> bool:
        # Fallback: no zGuard → no enforcement (open-core permissive path)
        return True
```

- **Open-core (no zGuard):** permissive no-op — any path loads, zOS is fully functional out of the box.
- **With zGuard installed:** the real policy (allowed directories, signature / hash checks) lives in the private `zguard.loader.plugin_trust` binary wheel. No call-site changes are needed to enable it.

---

## Contract

```
verify_plugin_trust(file_path, zos=None, logger=None) -> bool
```

- Returns `True` when the plugin is allowed to load.
- The zGuard implementation raises **`PluginTrustError`** when policy denies a path.
- That exception **must propagate unwrapped** so denials are visible. In `PythonModuleCache.load_and_cache`, `PluginTrustError` is re-raised *before* the generic `ValueError` wrapping; it is never swallowed. The `zLoader.load_plugins` best-effort loop (which logs-and-skips ordinary load failures) catches `PluginTrustError` **first and re-raises it** — a trust denial is a security event, not a routine failure, so it is never lumped in with "failed to load".

`PluginTrustError` is defined in `loader_constants` (subclass of `LoaderError`) and re-exported here, so the zGuard wheel can import and raise it.

---

## Call sites

The gate is called **before** any code executes, on every load path:

| Path | Gate call site |
|---|---|
| `.py` plugin | `PythonModuleCache.load_and_cache()` — before `spec.loader.exec_module(module)` |
| `.js` plugin | `PythonModuleCache.register_js_plugin()` — before registering the proxy |
| dotted module path | `zLoader.load_plugins()` — resolves the module origin via `importlib.util.find_spec` and gates **before** `importlib.import_module(path)` |

For the dotted path the gate is passed the resolved **origin file** (`spec.origin`) when available, so zGuard's path/signature policy applies to the actual file on disk; it falls back to the dotted name if the origin can't be resolved. `register_import_module()` is only the post-import cache step (the module has already passed the gate), so it carries no gate of its own.

> Note: resolving a deeply-nested dotted path can import parent packages during
> `find_spec`. The *leaf* module (the plugin) is never executed before the gate
> runs; sealing parent-package provenance is part of zGuard's policy.

---

## Handling denials

```python
from zOS.L1_Foundation.c_zLoader.loader_modules import PluginTrustError

try:
    z.loader.load_python_module("/untrusted/plugin.py")
except PluginTrustError as e:
    # Only raised when zGuard policy denies the path
    log.error("Plugin blocked by trust policy: %s", e)
```

---

## See Also

- [cache_plugin_GUIDE.md](cache_plugin_GUIDE.md) - The cache that calls the gate
- [constants_GUIDE.md](constants_GUIDE.md) - `PluginTrustError` in the exception hierarchy
- [../zLoader_GUIDE.md](../zLoader_GUIDE.md) - Plugin Management overview
