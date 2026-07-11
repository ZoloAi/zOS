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
      *.so | *.pyd
```

- `<platform-tag>` = `platform.system().lower()` + `-` + `platform.machine().lower()`
  - `darwin-arm64`, `darwin-x86_64`
  - `linux-x86_64`, `linux-aarch64`
  - `win-amd64`
- `<py-tag>` = `cp{sys.version_info.major}{sys.version_info.minor}` (`cp310`, `cp311`, `cp312`)

## How binaries land here

1. `zGuard` (private repo) builds per-platform wheels via
   `.github/workflows/build-wheels.yml` (`workflow_dispatch` or a `v*` tag).
2. Wheels are downloaded by hand from the Actions run artifacts.
3. The compiled `.so`/`.pyd` files are extracted and copied into the matching
   `<platform-tag>/<py-tag>/` folder here, replacing whatever version was
   there before ("whatever's in the folder wins" — no version selector yet).
4. Commit + push. That's the release.

## How `z patch` consumes this

At patch/install time, `z patch` computes the running machine's
`<platform-tag>/<py-tag>`, then fetches just that folder's files straight from
this repo on GitHub (no git clone, no full wheel download) and places them
where `import zguard` resolves. See `core/zSys/cli/patch_command.py`.

Dev mode (a local zGuard source checkout) bypasses this entirely — set
`ZGUARD_DEV_PATH` and `z patch` uses the editable source instead.
