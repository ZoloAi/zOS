# zos-plugin Compute Guide

> **Modules:** `core/zos_plugin/drivers.py`
> **Purpose:** The networking primitive behind `instance`/`proxy` — run / reach a zOS app instance through a swappable `ComputeDriver` (local process in dev, k8s in prod) so the wake/sleep/status flow never changes, only the backend does.

**[← Back to zos-plugin Guide](../zPlugin_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

"Run / reach another zOS app" is a *general* capability, so it lives in the SDK (not in any one app). A plugin asks for `instance`/`proxy` and gets a facade over the active `ComputeDriver`. An app to wake is described by an `AppSpec`; the driver returns an `Instance` value object whose `address` is where the live app is reachable.

```
instance.wake(app) ─► get_driver(zos) ─► ComputeDriver.wake(AppSpec) ─► Instance(state, address, ws_url)
                       (env-selected:        LocalProcessDriver (dev)
                        ZHOST_DRIVER →        K8sDriver (prod, registered later)
                        zos.config → local)
```

---

## Value objects

| Type | Fields / props |
|------|----------------|
| `AppSpec` | `app_id`, `folder`, `spark` (default `DEFAULT_SPARK = zSpark.zApp.zolo`), `host`; `spark_file` (tolerates a bare stem); `coerce(any)`; `from_spark_path(...)` |
| `Instance` | `app_id`, `state`, `host`, `port`, `ws_port`, `pid`; props `address` (`http://host:port`), `ws_url`, `running`; `as_dict()` |
| `ProxyTarget` | `app_id`, `state`, `url`, `ws_url`; `ready` (state == running) |

States are SSOT constants: `STATE_ASLEEP` / `STATE_WAKING` / `STATE_RUNNING` / `STATE_ERROR`.

`AppSpec.from_spark_path(app_id, spark_path, workspace_dir, store="zApps")` is the SSOT mapping a registry `zspark_path` (`zApps/<id>/zSpark.*.zolo`) → folder/spark, shared by the zProxy front door and the bundle store's `zspark_path`.

---

## `ComputeDriver` contract

```python
class ComputeDriver(abc.ABC):
    def wake(self, app: AppSpec, timeout=25.0) -> Instance: ...   # ensure running+reachable
    def sleep(self, app_id: str) -> bool: ...                      # tear down; True if stopped
    def status(self, app_id: str) -> Instance: ...                 # current state; never raises
```

---

## `LocalProcessDriver` (dev)

Each app instance is a **child `zolo` process** on its own ports:

- argv resolution: `ZHOST_ZOLO_BIN` env → `shutil.which("zolo")` → `[sys.executable, "-m", "zOS.main", spark]`. Always `shell=False` with a fixed binary — no shell, no test-derived string on the command line.
- per-instance ports (`_free_port`) are injected through the **OS environment** (the zEnv server-bind keys `HTTP_HOST`/`HTTP_PORT`/`WEBSOCKET_HOST`/`WEBSOCKET_PORT`) so the tenant's project folder is never mutated.
- the driver also stamps **`ZHOST_MANAGED=1`** on the child. That marker is what lets the injected host/port env **beat the tenant spark's own pins** — on a local machine the author's spark is king, but a hosted instance's network placement is the platform's business (zOS #28). This covers the zEnv side door that spark-stripping at push time can't reach.
- **per-build dependencies (zOS #26):** if the build carries a `zpackages/` directory (zpush installs the app's `zRequirements` there via `pip --target` at push time), the driver **prepends it to the child's `PYTHONPATH`** — tenant deps ride the build, the platform venv stays clean.
- started with `start_new_session=True`; `sleep()` `killpg`s the whole group (SIGTERM → wait 5s → SIGKILL) so re-exec'd children are reaped.
- `wake` is idempotent: a live+listening instance is returned as-is; a missing spark → `STATE_ERROR`; a process that exits early → `STATE_ERROR` with the log path (dead-child log capture: the tail of a failed boot is preserved for the failure sink); healthy → `STATE_RUNNING`; timed-out-but-alive → `STATE_WAKING`.

> **Trust boundary (T1).** Waking an app *runs its code*. `LocalProcessDriver` copies the host environment into the child **minus the keys the platform zEnv marks as its own** (`ZENV_EXPORTED_KEYS` are scrubbed before injection — tenant children don't inherit platform secrets), and applies **no sandbox** beyond that — appropriate for dev/self-hosted where the registry supplying `folder` is trusted. Multi-tenant isolation (scoped env, network, FS limits) is the **prod driver's** job (k8s/pod) — the V3 concern owned by zCloud + the zGuard-sealed runtime, not this dev driver.

---

## Driver registry

Env selects the backend; one instance per driver name is reused so the in-process instance table survives across plugin calls in the same host process.

```python
register_driver("k8s", K8sDriver)            # prod registers later, callers unchanged
drv = get_driver(zos)                          # ZHOST_DRIVER env → zos.config → "local"
```

---

## Troubleshooting

**`zSpark not found`** — `AppSpec.folder/spark` don't resolve to an existing file; check the registry row / `from_spark_path` mapping.

**`instance exited early (code N); see <log>`** — the child crashed on boot; read the per-instance log under the runtime dir (`$TMPDIR/zhost/<app_id>/`).

**Stuck in `waking`** — the port never opened within `timeout`; raise the timeout or inspect the log.

---

## See Also

- [zos-plugin Guide](../zPlugin_GUIDE.md) · [facades_GUIDE.md](facades_GUIDE.md) (`instance`/`proxy`)
- [hosting_GUIDE.md](hosting_GUIDE.md) — `ReleaseManager` drives this driver for blue/green
