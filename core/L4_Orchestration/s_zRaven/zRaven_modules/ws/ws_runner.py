# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/ws/ws_runner.py
"""ZRaven — WS + Browser test runner for Bifrost apps.

Transport contexts:
  WS layer   — zBoot, zExecute, zSubmit, zAssert.ws  (WebSocket protocol)
  Browser    — zOpen, zViewport, zType, zClick, zWait, zShot, zDrag (Playwright)

zOpen: zSpark is the SSOT for URL resolution — no URL args required.
"""

from __future__ import annotations

import asyncio
import json
import os as _os
import re as _re
import time as _time
import uuid
from pathlib import Path

from zSys import zpath  # zPath grammar — Layer-0 SSOT for sigil/segment decomposition
from typing import Any

try:
    import websockets
except ImportError:
    print("ERROR: websockets not found — reinstall zOS: pip install zos", flush=True)
    raise

from zOS.L1_Foundation.a_zConfig.zConfig_modules.loggers.app_emit import APP_LOG_EVENT

from ..base_runner import BaseStepRunner
from ..constants import MODE_BIFROST as _MODE_BIFROST
from ..utils.colors import CYAN, RESET, BOLD
from ..utils.parser import strip_sel as _strip_sel
from ..utils.reporter import info
from ..utils.viewport import (
    VIEWPORT_MOBILE_FALLBACK,
    classify_viewport,
    is_browser_block,
    is_ws_block,
    viewport_size,
)
from ..utils.data_manager import prepare_test_data, teardown_test_data
from ..assertions.evaluator import evaluate_assert

# WS protocol opcodes are owned by the bifrost bridge (compiled). The headless
# WS layer (zBoot/zExecute/zSubmit) drives a bifrost server, which only runs
# when zGuard is present — so these names resolve in any real WS test run.
# Browser/CLI tests never reach this layer and are unaffected if zguard is absent.
try:
    from zguard.bifrost.zBifrost_modules.bifrost_constants import (
        OP_EXECUTE_WALKER,
        OP_EXECUTE_ZFUNC,
        OP_EXECUTE_ZFUNC_RESPONSE,
        OP_WIZARD_GATE_SUBMIT,
        OP_WIZARD_GATE_RESULT,
        OP_RENDER_CHUNK,
        OP_ZFUNC_EXEC,
    )
    _WS_PROTO_AVAILABLE = True
except ImportError:
    _WS_PROTO_AVAILABLE = False
    OP_EXECUTE_WALKER = OP_EXECUTE_ZFUNC = OP_EXECUTE_ZFUNC_RESPONSE = None
    OP_WIZARD_GATE_SUBMIT = OP_WIZARD_GATE_RESULT = None
    OP_RENDER_CHUNK = OP_ZFUNC_EXEC = None

_WS_PROTO_REQUIRED = (
    "WS-layer zRaven steps (zBoot/zExecute/zSubmit) require zGuard. Run: z patch\n"
    "Browser (zOpen/zClick/…) and CLI tests are unaffected."
)

_ZBADGE_HIDE = (
    "const s = document.createElement('style');"
    "s.textContent = 'zBifrostBadge, [data-zbifrost-badge] { display: none !important; }';"
    "document.head ? document.head.appendChild(s) : "
    "document.addEventListener('DOMContentLoaded', () => document.head.appendChild(s));"
)

# Clear bifrost rendered cache on every page load so the full dashboard structure
# is always rebuilt from the server (prevents zDash-container missing on 2nd+ goto).
# IndexedDB.deleteDatabase blocks subsequent open() calls until deletion completes,
# so bifrost_client.js always starts with an empty cache on each navigation.
_ZCACHE_CLEAR = (
    "try { localStorage.clear(); sessionStorage.clear(); } catch(e) {}"
    "try { indexedDB.deleteDatabase('zBifrost_cache'); } catch(e) {}"
)

# ── Built-in Bifrost readiness (used by _run_open) ────────────────────────────
# zbase.css is now injected server-side as a <link> — CSS is synchronous with
# page load, no async fetch. We only need to wait for WS-rendered content.
_BIFROST_CONTENT_SELECTOR = "input[name], [data-dialog-id], .zDash-container"
_BIFROST_READY_TIMEOUT_MS = 12_000   # 12s — generous for WS render latency
# Pre-screenshot settle: lets the browser reflow/repaint after content lands.
_SHOT_SETTLE_MS           = 300


# ── Value generators for ~tokens in zType.value ──────────────────────────────
# Usage in .zolo:  value: ~email   →  zraven_<ts>@test.local
# Supported tokens: ~email  ~name  ~phone  ~company  ~text  ~int  ~uuid  ~bool

def _gen_ts() -> str:
    """Short timestamp suffix for unique values."""
    return str(int(_time.time() * 1000))[-7:]


# Field-name fragments that mark a value as sensitive (kept out of logs).
_SECRET_HINTS = ("pass", "pwd", "secret", "token", "otp", "pin", "apikey", "api_key", "credential")


def _looks_secret(label: Any) -> bool:
    low = str(label).lower()
    return any(h in low for h in _SECRET_HINTS)

_VALUE_GENERATORS: dict[str, Any] = {
    "email":   lambda: f"zraven_{_gen_ts()}@test.local",
    "name":    lambda: f"Raven {_gen_ts()}",
    "phone":   lambda: f"555-{_gen_ts()[-4:]}",
    "company": lambda: f"Corp {_gen_ts()[-5:]}",
    "text":    lambda: f"zraven_{_gen_ts()}",
    "int":     lambda: _gen_ts(),
    "uuid":    lambda: str(uuid.uuid4()),
    "bool":    lambda: "true",
}

# Bifrost step primitives in execution order. A single step may carry more than
# one primitive (a "compound" step, e.g. zViewport + zShot, or zClick + zWait);
# they run in this fixed order so authoring intent is deterministic. zLogger and
# zAssert are handled separately (assertions, not actions).
_BIFROST_PRIMITIVE_ORDER = (
    "zViewport", "zOpen", "zBoot", "zExecute", "zFetch", "zClean",
    "zType", "zUpload", "zClick", "zDrag", "zSubmit", "zHistory",
    "zWait", "zShot", "zScreenshot", "zMarker",
)
# Deprecated primitive aliases → canonical grammar key. Recognized so strict mode
# does not fail legacy suites, but a one-line warning nudges migration.
_DEPRECATED_PRIMITIVE_ALIASES = {"zScreenshot": "zShot"}
# Keys that are legal on a step but are not action primitives.
_BIFROST_NON_PRIMITIVE_KEYS = frozenset({"zAssert", "zLogger", "zCLI", "zBifrost"})


class ZRaven(BaseStepRunner):
    """WS + Browser runner. Instantiate, then call asyncio.run(runner.run(test_blocks))."""

    def __init__(
        self,
        ws_url: str,
        http_url: str,
        timeout: float = 10.0,
        spark_boot: dict | None = None,
        raven_file: str = "",
        stop_on_error: bool = True,
        raven_opts: dict | None = None,
        routes_table: dict | None = None,
    ) -> None:
        super().__init__(stop_on_error=stop_on_error)
        self.ws_url          = ws_url
        self.http_url        = http_url
        self.timeout         = timeout
        self.spark_boot      = spark_boot or {}
        # Live server route table (SSOT) for structured zOpen resolution.
        self._routes_table   = routes_table or {}
        self._raven_opts     = raven_opts or {}
        # Safe-by-default: zFetch/zOpen may only target the app's own origin.
        # Opt in with zRavenOptions.allow_external: true to hit other hosts.
        self._allow_external = bool(self._raven_opts.get("allow_external", False))
        # Strict mode (default on): unknown/empty steps fail instead of silently
        # passing. Opt out with zRavenOptions.strict: false.
        self._strict         = bool(self._raven_opts.get("strict", True))
        self._zraven_file    = raven_file
        self._ws             = None
        self._page: Any      = None
        self._pw: Any        = None
        self._browser: Any   = None
        self._context: Any   = None
        self._viewport_mode: str | None = None
        self._last_response: dict = {}
        self._app_log_buffer: list[dict] = []
        # Per-run generated values: step_key → resolved string (for $ref lookups + zClean)
        self._test_vars: dict[str, str] = {}
        # Last HTTP fetch response (status + body) for zAssert.api checks
        self._last_api_response: dict = {}

    # ── Origin guard (SSRF / arbitrary-navigation containment) ──────────────

    _LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", ""})

    def _origin_allowed(self, url: str) -> bool:
        """True if *url* may be fetched/opened.

        Relative URLs (resolved against the app origin) are always allowed.
        Absolute URLs are allowed only when they target the app's own host
        (loopback variants are treated as equivalent) unless the test opts in
        with zRavenOptions.allow_external: true.
        """
        if self._allow_external:
            return True
        if not str(url).lower().startswith(("http://", "https://")):
            return True
        from urllib.parse import urlparse  # pylint: disable=import-outside-toplevel
        try:
            target_host = (urlparse(url).hostname or "").lower()
            base_host   = (urlparse(self.http_url).hostname or "").lower()
        except Exception:  # pylint: disable=broad-except
            return False
        if target_host == base_host:
            return True
        return target_host in self._LOOPBACK_HOSTS and base_host in self._LOOPBACK_HOSTS

    # ── Browser lifecycle ──────────────────────────────────────────────────

    async def _ensure_browser(self) -> None:
        if self._page:
            return
        try:
            from playwright.async_api import async_playwright  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise RuntimeError("Browser engine not found. Run: playwright install chromium")

        import pathlib as _pl, glob as _glob, platform as _platform, sys as _sys  # pylint: disable=import-outside-toplevel
        env = _os.environ
        ep  = env.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if ep:
            mach      = _platform.machine().lower()
            plat_slug = (
                "mac-arm64" if _sys.platform == "darwin" and mach in ("arm64", "aarch64")
                else "mac-x64" if _sys.platform == "darwin"
                else "linux-arm64" if mach in ("arm64", "aarch64")
                else "linux-x64"
            )
            pattern  = f"{ep}/**/chrome-headless-shell-{plat_slug}/chrome-headless-shell"
            if not _glob.glob(pattern, recursive=True):
                for fallback in [
                    _pl.Path.home() / "Library/Caches/ms-playwright",
                    _pl.Path.home() / ".cache/ms-playwright",
                ]:
                    if _glob.glob(f"{fallback}/**/chrome-headless-shell-{plat_slug}/chrome-headless-shell", recursive=True):
                        env["PLAYWRIGHT_BROWSERS_PATH"] = str(fallback)
                        break

        self._pw      = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._page    = await self._browser.new_page()
        await self._page.add_init_script(_ZBADGE_HIDE)
        await self._page.add_init_script(_ZCACHE_CLEAR)
        self._page.on("console", self._on_console_message)

    async def _close_browser(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # ── WS helpers ────────────────────────────────────────────────────────

    async def _wait_for(self, *event_names: str) -> dict:
        deadline = asyncio.get_event_loop().time() + self.timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Timed out waiting for {event_names}")
            raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            ev  = msg.get("event") or msg.get("result")
            if ev in event_names:
                return msg
            if ev == APP_LOG_EVENT:
                self._app_log_buffer.append({
                    "message": msg.get("message", ""),
                    "level":   str(msg.get("level", "INFO")).upper(),
                    "tag":     msg.get("tag"),
                })
            elif ev not in (OP_RENDER_CHUNK, OP_ZFUNC_EXEC):
                info(f"[skip] {ev}: {str(msg)[:100]}")

    # ── Step handlers — HTTP fetch (for zAPI testing) ────────────────────

    async def _run_fetch(self, cfg: dict) -> bool:
        """
        Pure-Python HTTP request (no browser required).

        zFetch:
          url:     /api/crm/Overview/Search_Contacts   # relative or absolute
          method:  GET                                 # default GET
          headers:                                     # optional dict
            X-API-Key: my-key
          params:                                      # GET query-string dict
            query: alice
          body:                                        # POST/PUT JSON body dict
            name: Alice
            email: alice@example.com

        Populates self._last_api_response:
          {status: int, body: str, json: dict|None}
        """
        import urllib.request as _ureq
        import urllib.parse  as _uparse
        import urllib.error  as _uerr

        base   = self.http_url.rstrip("/")
        url    = str(cfg.get("url", "/"))
        if not url.startswith("http"):
            url = base + ("" if url.startswith("/") else "/") + url

        if not self._origin_allowed(url):
            reason = (f"zFetch blocked external URL {url!r} — set "
                      f"zRavenOptions.allow_external: true to permit cross-origin requests")
            info(reason)
            self._last_api_response = {"status": 0, "body": reason, "json": None}
            return False

        method  = str(cfg.get("method", "GET")).upper()
        headers = cfg.get("headers") or {}
        params  = cfg.get("params")  or {}
        body    = cfg.get("body")    or {}

        # Resolve $ref values from _test_vars (e.g. $Add_Contact_Email)
        def _resolve(val: Any) -> Any:
            if isinstance(val, str) and val.startswith("$"):
                return self._test_vars.get(val[1:], val)
            if isinstance(val, dict):
                return {k: _resolve(v) for k, v in val.items()}
            return val

        params = _resolve(params)
        body   = _resolve(body)

        if params:
            url = url + "?" + _uparse.urlencode(params)

        info(f"http.{method.lower()} → {url}")

        body_bytes = None
        if method in ("POST", "PUT", "PATCH") and body:
            body_bytes = json.dumps(body).encode("utf-8")
            if "Content-Type" not in headers:
                headers = dict(headers, **{"Content-Type": "application/json"})

        req = _ureq.Request(url, data=body_bytes, method=method, headers=headers)

        try:
            with _ureq.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
                self._last_api_response = {
                    "status": resp.status,
                    "body":   raw,
                    "json":   parsed,
                }
                return True
        except _uerr.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            self._last_api_response = {
                "status": exc.code,
                "body":   raw,
                "json":   parsed,
            }
            return True   # we captured the response; assertion decides pass/fail
        except Exception as exc:
            self._last_api_response = {"status": 0, "body": str(exc), "json": None}
            return False

    # ── Step handlers — browser ───────────────────────────────────────────

    @staticmethod
    def _zpath_tail(value: Any) -> str:
        """Normalize a zPath (or list of one) to its dotted tail for comparison.
        Accepts '@.zLoom.zUI.public.public_user' or ['@...'] → 'zUI.public.public_user'.
        """
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        return zpath.strip_symbol(str(value or ""))

    def _url_from_descriptor(self, cfg: dict) -> str:
        """Resolve a structured zOpen descriptor → URL path, using the live route
        table (SSOT). Mirrors zServer route grammar:

            zOpen: {type: zSpark}                              → default route "/"
            zOpen: {type: zLoom, zLoom: <zPath>, params: {..}} → matched pattern, filled
            zOpen: {type: zWalker, zUI: <zPath>}               → matched page route

        Match is by zLoom/zUI zPath tail; %name and :name params are substituted.
        """
        routes = self._routes_table or {}
        rtype  = str(cfg.get("type", "")).strip().lower()

        # type: zSpark → the spark-default route (_normalize_zspark_routes tags it), else "/".
        if rtype in ("zspark", "spark"):
            for path, rc in routes.items():
                if isinstance(rc, dict) and rc.get("_zspark_default"):
                    return path
            return "/"

        want_inja = self._zpath_tail(cfg.get("zLoom")) if cfg.get("zLoom") else ""
        want_view = self._zpath_tail(cfg.get("zUI") or cfg.get("zVaFile"))
        match_path = None
        for path, rc in routes.items():
            if not isinstance(rc, dict):
                continue
            if want_inja and self._zpath_tail(rc.get("zLoom")) == want_inja:
                match_path = path
                break
            if want_view and self._zpath_tail(rc.get("zVaFile") or rc.get("zUI")) == want_view:
                match_path = path
                break
        if match_path is None:
            match_path = str(cfg.get("path") or "/")

        for k, v in (cfg.get("params") or {}).items():
            match_path = match_path.replace(f"%{k}", str(v)).replace(f":{k}", str(v))
        return match_path if match_path.startswith("/") else "/" + match_path

    async def _run_open(self, route: Any) -> bool:
        await self._ensure_browser()
        base = self.http_url.rstrip("/")
        if isinstance(route, dict):
            url = base + self._url_from_descriptor(route)
        elif route is True or str(route).strip().lower() == "zspark":
            url = base + "/"
        elif isinstance(route, str) and zpath.is_zpath(route):
            # String zPath zOpen → resolve through the route-table SSOT (same as
            # a {type: zWalker, zUI: <zPath>} descriptor) instead of a structural
            # dots→slashes guess against a stale folder literal.
            url = base + self._url_from_descriptor({"type": "zWalker", "zUI": route})
        elif isinstance(route, str) and not route.startswith("http"):
            url = base + "/" + str(route).lstrip("/")
        else:
            url = str(route)

        if not self._origin_allowed(url):
            reason = (f"zOpen blocked external URL {url!r} — set "
                      f"zRavenOptions.allow_external: true to permit cross-origin navigation")
            info(reason)
            self._last_response = {"event": "open_failed", "error": reason}
            return False

        info(f"browser.open → {url}")

        await self._page.goto(url, wait_until="networkidle")

        # ── Bifrost content readiness ─────────────────────────────────────────
        # zbase.css is now a server-side <link> — synchronous with page load,
        # no async CDN fetch needed. We only wait for WS-rendered content.
        content_found = False
        try:
            await self._page.wait_for_selector(
                _BIFROST_CONTENT_SELECTOR, state="visible",
                timeout=_BIFROST_READY_TIMEOUT_MS,
            )
            content_found = True
        except Exception:
            pass  # page has no dialogs/inputs — continue gracefully

        # ── Diagnostic console log ────────────────────────────────────────────
        try:
            diag = await self._page.evaluate("""() => ({
                zbaseLink:      !!document.querySelector('link[href*="zbase.css"]'),
                zCanvas:        !!document.querySelector('link[href*="zCanvas.css"]'),
                dashContainer:  !!document.querySelector('.zDash-container'),
                contentVisible: !!document.querySelector('input[name], [data-dialog-id], .zDash-container'),
                viewport:       `${window.innerWidth}x${window.innerHeight}`,
            })""")
            parts = [f"viewport={diag['viewport']}"]
            if not diag['zbaseLink']:  parts.append("⚠ zbase.css link missing")
            if not diag['zCanvas']:    parts.append("⚠ zCanvas.css missing")
            if not diag['dashContainer']: parts.append("⚠ .zDash-container missing")
            if not diag['contentVisible']: parts.append("⚠ no content found")
            info(f"  page ready [{', '.join(parts)}]")
        except Exception:
            pass


        self._last_response = {"event": "page_loaded", "url": url}
        return True

    async def _run_viewport(self, spec: Any) -> bool:
        await self._ensure_browser()
        self._viewport_mode = classify_viewport(spec)

        # Always create a fresh context + page for every viewport change.
        # This gives each device test a clean WS handshake (zOS re-sends the
        # full zDash init sequence) and empty storage (no stale rendered cache).
        ctx_kwargs: dict = {}
        label: str = ""

        if isinstance(spec, str) and spec.lower() not in ("desktop", "mobile", "tablet"):
            # Named Playwright device (e.g. "iPhone 14")
            pw_devices  = self._pw.devices
            device_name = spec
            if device_name not in pw_devices:
                low   = device_name.lower()
                match = next((k for k in pw_devices if k.lower() == low), None)
                device_name = match or device_name
            if device_name in pw_devices:
                ctx_kwargs = dict(pw_devices[device_name])
                label = f"{device_name} ({self._viewport_mode})"
            else:
                fw, fh = VIEWPORT_MOBILE_FALLBACK
                ctx_kwargs = {"viewport": {"width": fw, "height": fh}}
                label = f"device '{spec}' not found → {fw}×{fh}"
        elif isinstance(spec, (list, tuple)) and len(spec) >= 2:
            w, h = int(spec[0]), int(spec[1])
            ctx_kwargs = {"viewport": {"width": w, "height": h}}
            label = f"{w}×{h} ({self._viewport_mode})"
        else:
            w, h  = viewport_size(spec)
            ctx_kwargs = {"viewport": {"width": w, "height": h}}
            label = f"{spec} {w}×{h}"

        # Tear down previous context (or the default browser.new_page context)
        if self._context:
            await self._context.close()
            self._context = None
        elif self._page:
            await self._page.close()

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._page    = await self._context.new_page()
        await self._page.add_init_script(_ZBADGE_HIDE)
        await self._page.add_init_script(_ZCACHE_CLEAR)
        self._page.on("console", self._on_console_message)
        info(f"viewport → {label}")

        self._last_response = {"event": "viewport_set", "mode": self._viewport_mode}
        return True

    async def _run_shot(self, cfg: dict, step_name: str = "zShot") -> bool:
        await self._ensure_browser()

        raven_dir  = _os.path.dirname(_os.path.abspath(self._zraven_file)) if self._zraven_file else "zRaven"
        raven_name = _os.path.basename(self._zraven_file or "zRaven.unknown.zolo")
        raven_name = raven_name.removeprefix("zRaven.").removesuffix(".zolo")

        shots_root = _os.path.join(
            raven_dir, "zShots", raven_name,
            self._viewport_mode if self._viewport_mode else "",
        ).rstrip("/")

        full_page   = cfg.get("full_page", False)
        fmt         = cfg.get("format", "png")
        quality     = cfg.get("quality", 90)
        selector    = cfg.get("selector")
        delay_ms    = cfg.get("delay", 0)
        overwrite   = cfg.get("overwrite", True)
        resolution  = cfg.get("resolution")
        burst_cfg   = cfg.get("burst")
        # timestamp_shots: keep a dated history of screenshots each run.
        # Set via zRavenOptions.timestamp_shots: true or per-step shot.timestamp.
        use_ts      = cfg.get("timestamp", self._raven_opts.get("timestamp_shots", False))

        # Built-in settle: sleep for explicit delay OR default, then wait for
        # two rAF cycles so the browser has painted after any pending style recalc.
        await asyncio.sleep((delay_ms or _SHOT_SETTLE_MS) / 1000)
        try:
            await self._page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
        except Exception:
            pass
        if resolution:
            await self._page.set_viewport_size({"width": int(resolution[0]), "height": int(resolution[1])})

        def _shot_path(base_dir: str, name: str, idx: int | None = None) -> str:
            ts_suffix = ""
            if use_ts or not overwrite:
                ts_suffix = "_" + _time.strftime("%Y%m%d_%H%M%S")
            if idx is not None:
                filename = f"{name}{ts_suffix}_{idx}.{fmt}"
            else:
                filename = f"{name}{ts_suffix}.{fmt}"
            return _os.path.join(base_dir, filename)

        shot_kwargs: dict = {"full_page": full_page}
        if fmt in ("jpeg", "webp"):
            shot_kwargs.update({"type": fmt, "quality": quality})

        saved: list[str] = []
        if burst_cfg:
            every_ms  = burst_cfg.get("every", 1000)
            count     = burst_cfg.get("count", 6)
            burst_dir = _os.path.join(shots_root, step_name)
            _os.makedirs(burst_dir, exist_ok=True)
            for i in range(1, count + 1):
                p = _shot_path(burst_dir, step_name, i)
                if selector:
                    el = await self._page.wait_for_selector(selector)
                    await el.screenshot(path=p, **{k: v for k, v in shot_kwargs.items() if k != "full_page"})
                else:
                    await self._page.screenshot(path=p, **shot_kwargs)
                saved.append(p)
                info(f"zShot burst {i}/{count} → {p}")
                if i < count:
                    await asyncio.sleep(every_ms / 1000)
        else:
            _os.makedirs(shots_root, exist_ok=True)
            p = _shot_path(shots_root, step_name)
            if selector:
                el = await self._page.wait_for_selector(_strip_sel(selector))
                await el.screenshot(path=p, **{k: v for k, v in shot_kwargs.items() if k != "full_page"})
            else:
                await self._page.screenshot(path=p, **shot_kwargs)
            saved.append(p)
            info(f"zShot → {p}")

        self._last_response = {"event": "shot", "paths": saved}
        return True

    def _resolve_value(self, raw: Any, step_key: str = "") -> str:
        """Resolve a zType value:
          ~token   → generate unique value via _VALUE_GENERATORS
          $key     → look up previously resolved value from self._test_vars
          literal  → return as-is
        Generated values are stored in self._test_vars[step_key] for later $ref.
        """
        s = str(raw) if raw is not None else ""
        if s.startswith("~"):
            token = s[1:].lower()
            gen = _VALUE_GENERATORS.get(token)
            resolved = gen() if gen else s
            if step_key:
                self._test_vars[step_key] = resolved
            return resolved
        if s.startswith("$"):
            key = s[1:]
            return self._test_vars.get(key, s)
        if step_key:
            self._test_vars[step_key] = s
        return s

    async def _run_type(self, cfg: dict, step_key: str = "") -> bool:
        await self._ensure_browser()
        selector = _strip_sel(cfg["selector"])
        value    = self._resolve_value(cfg.get("value", ""), step_key)
        shown    = "***" if _looks_secret(selector) else f"{value!r}"
        info(f"browser.type → {selector} = {shown}")
        await self._page.fill(selector, value)
        self._last_response = {"event": "typed", "selector": selector, "value": value}
        return True

    async def _run_clean(self, cfg: dict) -> bool:
        """zClean: delete CSV rows matching criteria mid-test.
        cfg: {model: "contacts", match: {email: $Fill_Email}} or literal values.

        Fail-closed: an unsafe model name, a path that escapes Data/, or a write
        error fails the step (rather than silently corrupting / hiding the fault).
        A genuine no-op (missing file / nothing to match) still passes.

        Note: full Data/ restore happens automatically after run() via the
        Data/ swap, so zClean only matters for clean state WITHIN a run.
        """
        model = str(cfg.get("model", "")).strip()
        match = cfg.get("match", {})
        if not model or not match:
            return True
        # Contain the target: the model must be a bare CSV name, never a path.
        if not _re.fullmatch(r"[A-Za-z0-9_-]+", model):
            reason = f"zClean rejected unsafe model name {model!r}"
            info(reason)
            self._last_response = {"event": "clean_failed", "error": reason}
            return False
        resolved_match = {
            k: self._test_vars.get(v[1:], v) if isinstance(v, str) and v.startswith("$") else v
            for k, v in match.items()
        }
        info(f"zClean → {model} where {resolved_match}")
        app_dir = str(Path(self._zraven_file).parent.parent) if self._zraven_file else ""
        if not app_dir:
            return True
        data_dir = (Path(app_dir) / "Data").resolve()
        csv_path = (data_dir / f"{model}.csv").resolve()
        if data_dir != csv_path.parent:
            reason = f"zClean refused path outside Data/: {csv_path}"
            info(reason)
            self._last_response = {"event": "clean_failed", "error": reason}
            return False
        if not csv_path.exists():
            return True
        try:
            import csv as _csv, io as _io
            raw = csv_path.read_text(encoding="utf-8")
            reader = _csv.DictReader(_io.StringIO(raw))
            rows = [r for r in reader if not all(r.get(k) == v for k, v in resolved_match.items())]
            out = _io.StringIO()
            if reader.fieldnames:
                writer = _csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            csv_path.write_text(out.getvalue(), encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            reason = f"zClean failed to rewrite {csv_path.name}: {exc}"
            info(f"⚠ {reason}")
            self._last_response = {"event": "clean_failed", "error": reason}
            return False
        self._last_response = {"event": "cleaned", "model": model}
        return True

    async def _run_click(self, cfg: dict) -> bool:
        await self._ensure_browser()
        selector = _strip_sel(cfg["selector"])
        info(f"browser.click → {selector}")
        await self._page.click(selector)
        await asyncio.sleep(0.2)
        self._last_response = {"event": "clicked", "selector": selector}
        return True

    async def _run_wait(self, cfg: dict) -> bool:
        await self._ensure_browser()
        selector = _strip_sel(cfg.get("selector", ""))
        state    = cfg.get("state", "visible")
        timeout  = cfg.get("timeout", self.timeout * 1000)
        info(f"browser.wait → {selector} ({state})")
        try:
            if state == "enabled":
                # Pass the selector as a JS arg (never interpolate into source) so
                # quotes/backslashes in the selector can't break out of the script.
                await self._page.wait_for_function(
                    "sel => { const el = document.querySelector(sel); return !!el && !el.disabled; }",
                    arg=selector,
                    timeout=timeout,
                )
            else:
                await self._page.wait_for_selector(selector, state=state, timeout=timeout)
        except Exception as exc:  # pylint: disable=broad-except
            self._last_response = {"event": "wait_failed", "error": str(exc)}
            return False
        self._last_response = {"event": "waited", "selector": selector}
        return True

    async def _run_upload(self, cfg: dict) -> bool:
        """zUpload: set a file on a file input (Playwright set_input_files).

        cfg: {selector: "input[name=avatar]", path: "zHerald_profile.jpg"}
        A relative path resolves against the app dir (zRaven file's grandparent),
        so tests can upload a fixture living anywhere in the app. Setting files
        fires the input's change event → the client's declarative zAPI upload.
        """
        await self._ensure_browser()
        selector = _strip_sel(cfg.get("selector", "input[type=file]"))
        path = cfg.get("path") or cfg.get("file") or ""
        p = Path(path)
        if path and not p.is_absolute() and self._zraven_file:
            cand = Path(self._zraven_file).parent.parent / path
            if cand.exists():
                p = cand
        info(f"browser.set_input_files → {selector} = {p}")
        if not p.exists():
            self._last_response = {"event": "upload_failed", "error": f"file not found: {p}"}
            return False
        try:
            await self._page.set_input_files(selector, str(p))
            await asyncio.sleep(0.6)  # let the change→fetch→img-swap settle
        except Exception as exc:  # pylint: disable=broad-except
            self._last_response = {"event": "upload_failed", "error": str(exc)}
            return False
        self._last_response = {"event": "uploaded", "selector": selector, "path": str(p)}
        return True

    async def _run_drag(self, cfg: dict) -> bool:
        await self._ensure_browser()
        selector = _strip_sel(cfg.get("selector", ""))
        from_pos = cfg.get("from", {})
        to_pos   = cfg.get("to", {})
        info(f"browser.drag → {selector}  {from_pos} → {to_pos}")
        element = await self._page.wait_for_selector(selector)
        box     = await element.bounding_box()
        sx = box["x"] + from_pos.get("x", 0)
        sy = box["y"] + from_pos.get("y", 0)
        ex = box["x"] + to_pos.get("x", 0)
        ey = box["y"] + to_pos.get("y", 0)
        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down()
        await asyncio.sleep(0.05)
        await self._page.mouse.move(ex, ey, steps=10)
        await asyncio.sleep(0.05)
        await self._page.mouse.up()
        await asyncio.sleep(0.2)
        self._last_response = {"event": "dragged", "selector": selector}
        return True

    async def _run_history(self, cfg: Any) -> bool:
        """zHistory: drive the browser Back/Forward buttons (popstate).

        cfg may be a bare string ("back" / "forward") or a dict {direction: back}.
        We invoke window.history.back()/forward() via evaluate rather than
        Playwright's page.go_back() because a zOS SPA never unloads the document on
        popstate — go_back() would block waiting for a navigation/load that never
        fires. evaluate fires popstate immediately; the following zWait synchronizes
        on the WS-rendered result (server-authoritative). SSOT contract:
          • back    → client sends a bare zBack intent; server pops its trail.
          • forward → client re-requests the destination URL as a fresh nav.
        """
        await self._ensure_browser()
        direction = (cfg.get("direction") if isinstance(cfg, dict) else cfg) or "back"
        direction = str(direction).strip().lower()
        info(f"browser.history → {direction}")
        if direction == "forward":
            await self._page.evaluate("() => window.history.forward()")
        else:
            await self._page.evaluate("() => window.history.back()")
        # Nudge: let popstate → WS round-trip start; the next zWait does the real sync.
        await asyncio.sleep(0.3)
        self._last_response = {"event": "history", "direction": direction}
        return True

    # ── Step handlers — WS ────────────────────────────────────────────────

    async def _run_boot(self, cfg: dict) -> bool:
        if "url" in cfg:
            await self._ensure_browser()
            url = cfg["url"]
            if url.startswith("/"):
                url = self.http_url.rstrip("/") + url
            info(f"browser.goto → {url}")
            await self._page.goto(url, wait_until="networkidle")
            self._last_response = {"event": "page_loaded", "url": url}
            return True
        if not _WS_PROTO_AVAILABLE:
            raise RuntimeError(_WS_PROTO_REQUIRED)
        req_id  = str(uuid.uuid4())[:8]
        payload = {
            "event":      OP_EXECUTE_WALKER,
            "zVaFolder":  cfg.get("zVaFolder", "@.UI"),
            "zVaFile":    cfg["zVaFile"],
            "zBlock":     cfg["zBlock"],
            "_requestId": req_id,
        }
        await self._ws.send(json.dumps(payload))
        info(f"execute_walker → {cfg['zVaFile']}#{cfg['zBlock']}")
        response = await self._wait_for("completed", "error", "aborted")
        self._last_response = response
        return response.get("result") == "completed"

    async def _run_execute(self, cfg: dict) -> bool:
        if not _WS_PROTO_AVAILABLE:
            raise RuntimeError(_WS_PROTO_REQUIRED)
        req_id = "zr-" + str(uuid.uuid4())[:8]
        fn     = cfg.get("fn", cfg.get("zfunc", ""))
        await self._ws.send(json.dumps({
            "event":     OP_EXECUTE_ZFUNC,
            "zfunc":     fn,
            "requestId": req_id,
        }))
        info(f"execute_zfunc → {fn}")
        response = await self._wait_for(OP_EXECUTE_ZFUNC_RESPONSE)
        self._last_response = response
        return response.get("success", False)

    async def _run_submit(self, cfg: dict) -> bool:
        if not _WS_PROTO_AVAILABLE:
            raise RuntimeError(_WS_PROTO_REQUIRED)
        await self._ws.send(json.dumps({
            "event":      OP_WIZARD_GATE_SUBMIT,
            "wizardPath": cfg.get("path", ""),
            "gateKey":    cfg.get("gate", ""),
            "value":      str(cfg.get("value", "")),
        }))
        _gate  = cfg.get("gate")
        _shown = "***" if _looks_secret(_gate) else cfg.get("value")
        info(f"wizard_gate_submit → gate={_gate}, value={_shown}")
        response = await self._wait_for(OP_WIZARD_GATE_RESULT, "error")
        self._last_response = response
        return "error" not in response

    # ── Browser console capture (for zLogger assertions) ──────────────────

    def _on_console_message(self, msg: Any) -> None:
        """Capture [zLog] console messages emitted by the zLogger client handler."""
        try:
            text = msg.text
            if not text.startswith("[zLog]"):
                return
            body  = text[len("[zLog]"):].strip()
            level = {
                "log":     "INFO",
                "warning": "WARNING",
                "error":   "ERROR",
                "debug":   "DEBUG",
            }.get(msg.type, "INFO")
            self._app_log_buffer.append({"message": body, "level": level, "tag": None})
        except Exception:
            pass

    # ── Step dispatcher ───────────────────────────────────────────────────

    async def _dispatch_primitive(self, key: str, val: Any, step_name: str) -> bool:
        """Run a single Bifrost action primitive. Returns True on success."""
        if key == "zViewport":
            return await self._run_viewport(val)
        if key == "zFetch":
            fetch_cfg = val if isinstance(val, dict) else {"url": str(val)}
            return await self._run_fetch(fetch_cfg)
        if key == "zOpen":
            return await self._run_open(val)
        if key == "zBoot":
            return await self._run_boot(val)
        if key == "zExecute":
            return await self._run_execute(val)
        if key == "zSubmit":
            return await self._run_submit(val)
        if key == "zType":
            return await self._run_type(val, step_key=step_name)
        if key == "zClean":
            return await self._run_clean(val)
        if key == "zClick":
            return await self._run_click(val)
        if key == "zWait":
            return await self._run_wait(val)
        if key in ("zShot", "zScreenshot"):
            if key == "zScreenshot":
                info("⚠ zScreenshot is deprecated — use zShot (grammar SSOT). "
                     "Taking screenshot; 'path' is ignored (shots save under zShots/).")
            shot_cfg = {} if val is True else (val if isinstance(val, dict) else {})
            return await self._run_shot(shot_cfg, step_name)
        if key == "zUpload":
            return await self._run_upload(val)
        if key == "zDrag":
            return await self._run_drag(val)
        if key == "zHistory":
            return await self._run_history(val)
        if key == "zMarker":
            label = str(val) if val is not True else step_name
            info(f"marker: {label}")
            return True
        return True

    async def run_step(self, step_name: str, step_cfg: dict) -> bool:
        # Step-level mode dispatch: zCLI:/zBifrost: keys route to the right runner.
        step_cfg = self._resolve_mode_step(step_cfg, _MODE_BIFROST)
        if step_cfg is None:
            return True  # CLI-only step — skip silently in Bifrost mode

        assert_cfg = step_cfg.get("zAssert", {})

        # zLogger is an assertion against the captured log buffer. It no longer
        # short-circuits the step, so a sibling zAssert on the same step still runs.
        if "zLogger" in step_cfg:
            from ..assertions.evaluator import evaluate_logger_assert  # pylint: disable=import-outside-toplevel
            passed, reason = evaluate_logger_assert(step_cfg["zLogger"], self._app_log_buffer)
            if not passed:
                self._record_fail(step_name, reason)
                return False

        # Compound steps: run every recognized primitive in a fixed order.
        ran_primitive = False
        for key in _BIFROST_PRIMITIVE_ORDER:
            if key not in step_cfg:
                continue
            ran_primitive = True
            ok = await self._dispatch_primitive(key, step_cfg[key], step_name)
            if not ok:
                self._record_fail(
                    step_name,
                    str(self._last_response.get("error", self._last_response.get("result", "step failed"))),
                )
                return False

        # Strict vocabulary check: a step with no recognized primitive, no
        # zAssert, and no zLogger is either a typo or a silent no-op. Fail loudly
        # rather than record a fake pass. Opt out with zRavenOptions.strict: false.
        if not ran_primitive and not assert_cfg and "zLogger" not in step_cfg:
            unknown = [k for k in step_cfg if k not in _BIFROST_NON_PRIMITIVE_KEYS]
            if self._strict:
                self._record_fail(
                    step_name,
                    f"no recognized zRaven primitive in step (keys: {unknown or ['<empty>']}) — "
                    f"set zRavenOptions.strict: false to allow no-op steps",
                )
                return False
            self._record_warn(step_name, f"no recognized primitive (keys: {unknown or ['<empty>']})")
            return True

        if assert_cfg:
            passed, reason = await evaluate_assert(
                assert_cfg, self._last_response, self._page,
                api_response=self._last_api_response,
            )
            if passed:
                self._record_pass(step_name)
            else:
                self._record_fail(step_name, reason)
            return passed

        self._record_pass(step_name)
        return True

    # ── Block + run ───────────────────────────────────────────────────────

    async def _exec_block(self, block_name: str, block_steps: dict) -> None:
        from ..utils.colors import YELLOW  # pylint: disable=import-outside-toplevel
        print(f"{BOLD}[ {block_name} ]{RESET}", flush=True)
        for step_name, step_cfg in block_steps.items():
            if self._done:
                break
            if not isinstance(step_cfg, dict):
                continue
            try:
                ok = await self.run_step(step_name, step_cfg)
            except asyncio.TimeoutError as exc:
                self._record_fail(step_name, f"TIMEOUT — {exc}")
                ok = False
            except Exception as exc:  # pylint: disable=broad-except
                self._record_fail(step_name, f"ERROR — {exc}")
                ok = False
            if not ok and self.stop_on_error:
                print(f"{YELLOW}⚡ stop_on_error: halted after first failure{RESET}", flush=True)
                self._done = True
                break
        print()

    def _inject_spark_boot(self, ws_blocks: dict) -> dict:
        if not self.spark_boot:
            return ws_blocks
        result = {}
        for block_name, block_steps in ws_blocks.items():
            has_boot = any("zBoot" in sc for sc in block_steps.values() if isinstance(sc, dict))
            if has_boot:
                result[block_name] = block_steps
            else:
                injected = {"_zBoot": {"zBoot": self.spark_boot, "zAssert": {"result": "completed"}}}
                injected.update(block_steps)
                result[block_name] = injected
        return result

    async def run(self, test_blocks: dict) -> bool:
        print(f"\n{BOLD}{CYAN}zRaven{RESET}  →  {self.ws_url}\n", flush=True)

        # Isolate Data/ — swap original to Data._zraven_bak/, run against fresh copy
        app_dir   = str(Path(self._zraven_file).parent.parent) if self._zraven_file else ""
        _isolated = prepare_test_data(app_dir) if app_dir else False
        if _isolated:
            info(f"data isolated: {app_dir}/Data/ (original safe in Data._zraven_bak/)")

        ws_blocks      = {k: v for k, v in test_blocks.items() if isinstance(v, dict) and not is_browser_block(v)}
        browser_blocks = {k: v for k, v in test_blocks.items() if isinstance(v, dict) and is_browser_block(v)}
        ws_blocks      = self._inject_spark_boot(ws_blocks)

        # Only open a bifrost WS connection when a block actually needs one.
        # HTTP-only suites (zFetch / zClean / zLogger) run without a server.
        needs_ws = any(is_ws_block(v) for v in ws_blocks.values())

        try:
            if ws_blocks and needs_ws:
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    for block_name, block_steps in ws_blocks.items():
                        await self._exec_block(block_name, block_steps)
            elif ws_blocks:
                for block_name, block_steps in ws_blocks.items():
                    await self._exec_block(block_name, block_steps)

            if browser_blocks:
                try:
                    for block_name, block_steps in browser_blocks.items():
                        await self._exec_block(block_name, block_steps)
                finally:
                    await self._close_browser()
        finally:
            if _isolated:
                teardown_test_data(app_dir)
                info(f"data restored: {app_dir}/Data/")

        self.print_summary()
        return self.failed == 0
