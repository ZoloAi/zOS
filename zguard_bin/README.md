# zguard_bin/

Closed-core compiled `zguard` binaries (`.so` / `.pyd`), one folder per
platform+arch, one subfolder per Python ABI. Git-tracked in this public repo
so `z patch` can live-fetch exactly the file a given machine needs — nothing
here is ever bundled into the `zolo-os` wheel or sdist (see `MANIFEST.in` and
`setup.py`).

## Layout

```
zguard_bin/
  <platform-tag>/
    <py-tag>/
      VERSION          -- one line, mirrors zguard's package version
      MANIFEST.txt      -- one relative path per line, everything to fetch
      zguard/           -- the actual package: __init__.py (source) +
                           compiled *.so / *.pyd submodules, no other .py
                           source and no .c intermediates
```

- `<platform-tag>` = `platform.system().lower()` + `-` + `platform.machine().lower()`
  - `darwin-arm64`, `darwin-x86_64`
  - `linux-x86_64`, `linux-aarch64`
  - `win-amd64`
- `<py-tag>` = `cp{sys.version_info.major}{sys.version_info.minor}` (`cp310`, `cp311`, `cp312`)

The `zguard/` subfolder is deliberately one level down from `<py-tag>/` so
the *parent* of `zguard/` can be dropped straight onto `sys.path` -- both
here (git checkout) and in the per-user fetch cache (see below) -- with zero
restructuring at either end.

## How binaries land here

1. `zGuard` (private repo) builds per-platform wheels via
   `.github/workflows/build-wheels.yml` (`workflow_dispatch` or a `v*` tag).
2. Wheels are downloaded by hand from the Actions run artifacts.
3. The compiled `.so`/`.pyd` files (+ thin `__init__.py` re-export shims) are
   extracted -- never the plain `.py` source or `.c` intermediates the wheel
   also contains -- into the matching `<platform-tag>/<py-tag>/zguard/`
   folder here, replacing whatever was there before. `VERSION` and
   `MANIFEST.txt` get regenerated alongside it.
4. Commit + push. That's the release ("whatever's in the folder wins" — no
   version selector yet, bump `VERSION` when it actually matters).

## How `z patch` consumes this

See `core/zSys/cli/zguard_provision.py` for the full three-way branch. In
short: at every boot, `ensure_zguard_importable()` computes the running
machine's `<platform-tag>/<py-tag>`, and either
  - uses a local source checkout if `ZGUARD_DEV_PATH` is set, or
  - trusts an already-fetched cache under zMachine's user-data dir if its
    `VERSION` matches this repo's, or
  - fetches `VERSION` + `MANIFEST.txt` + every listed file via plain HTTPS
    GET from `raw.githubusercontent.com` (no git clone, no full wheel
    download) straight into that cache.

`z patch` (`core/zSys/cli/patch_command.py`) drives the same logic explicitly
and falls back to reinstalling onto a supported Python version via `uv` if
the running interpreter's ABI isn't one we ship a build for at all.
