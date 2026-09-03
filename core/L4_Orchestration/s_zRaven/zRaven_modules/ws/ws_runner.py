# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/ws/ws_runner.py
"""ZRaven — WS + Browser test runner for Bifrost apps.

Transport contexts:
  WS layer   — zBoot, zExecute, zSubmit, zAssert.ws  (WebSocket protocol)
  Browser    — zOpen, zViewport, zType, zClick, zWait, zCapture, zShot, zDrag (Playwright)

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
from ..utils.reporter import info, warn_step
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


def _prune_old_shots(base_dir: str, name: str, fmt: str, keep: int) -> None:
    """Keep only the ``keep`` most recent timestamped runs of a shot step.

    Every filename a single run writes for ``name`` shares one mm-dd-HH-MM
    prefix (a burst run writes several files under that same prefix) — group
    matches by that prefix, rank groups by the mtime of their newest file,
    and delete every file outside the top ``keep`` groups. Runs BEFORE the
    new shot is written so a step's history never exceeds the cap even
    mid-run. Best-effort: a stray permissions/OS error on one file is
    swallowed so a prune hiccup never fails the actual test step.
    """
    import glob as _glob  # pylint: disable=import-outside-toplevel

    pattern = _os.path.join(base_dir, f"[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9]_{name}*.{fmt}")
    matches = _glob.glob(pattern)
    if len(matches) <= keep:
        return

    groups: dict[str, list[str]] = {}
    for path in matches:
        prefix = _os.path.basename(path)[:11]  # "MM-DD-HH-MM"
        groups.setdefault(prefix, []).append(path)

    ranked = sorted(
        groups.items(),
        key=lambda kv: max(_os.path.getmtime(p) for p in kv[1]),
        reverse=True,
    )
    for _, stale_paths in ranked[keep:]:
        for stale_path in stale_paths:
            try:
                _os.remove(stale_path)
            except OSError:
                pass


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
    "zType", "zFill", "zUpload", "zClick", "zPick", "zDrag", "zSubmit", "zHistory",
    "zWait", "zCapture", "zShot", "zScreenshot", "zMarker",
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

        import pathlib as _pl, glob as _glob  # pylint: disable=import-outside-toplevel
        from zSys.platform_identity import playwright_slug  # pylint: disable=import-outside-toplevel
        env = _os.environ
        ep  = env.get("PLAYWRIGHT_BROWSERS_PATH", "")
        plat_slug = playwright_slug()
        if ep and plat_slug:
            # Playwright names the shell binary chrome-headless-shell.exe on
            # Windows; glob with a wildcard suffix so one pattern covers both.
            pattern  = f"{ep}/**/chrome-headless-shell-{plat_slug}/chrome-headless-shell*"
            if not _glob.glob(pattern, recursive=True):
                _home = _pl.Path.home()
                for fallback in [
                    _home / "Library/Caches/ms-playwright",            # macOS
                    _home / ".cache/ms-playwright",                    # Linux
                    _home / "AppData/Local/ms-playwright",             # Windows
                ]:
                    if _glob.glob(f"{fallback}/**/chrome-headless-shell-{plat_slug}/chrome-headless-shell*", recursive=True):
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
        # $var URL — a value lifted off the page by zCapture (zOS#98), e.g. a
        # minted share link. Unknown var fails loud, never fetches literally.
        if url.startswith("$"):
            captured = self._test_vars.get(url[1:])
            if captured is None:
                reason = f"zFetch url {url!r} — no captured value (add a zCapture step first)"
                info(reason)
                self._last_api_response = {"status": 0, "body": reason, "json": None}
                return False
            url = str(captured)
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

    @staticmethod
    def _view_stem(value: Any) -> str:
        """Normalize a page reference to its zUI file stem for route matching.

        '@.zViews.zAccount.zUI.Login'        → 'zUI.Login'
        '@.zViews.zAccount.zUI.Login.Login'  → 'zUI.Login'   (trailing block ignored)
        'zUI.Login'                          → 'zUI.Login'   (route-table zVaFile)
        """
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        segs = zpath.split(str(value or "")).segments
        for i, seg in enumerate(segs):
            if seg == "zUI" and i + 1 < len(segs):
                return f"zUI.{segs[i + 1]}"
        return ".".join(segs)

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
        want_view = self._view_stem(cfg.get("zUI") or cfg.get("zVaFile"))
        match_path = None
        for path, rc in routes.items():
            if not isinstance(rc, dict):
                continue
            if want_inja and self._zpath_tail(rc.get("zLoom")) == want_inja:
                match_path = path
                break
            if want_view and self._view_stem(rc.get("zVaFile") or rc.get("zUI")) == want_view:
                match_path = path
                break
        if match_path is None:
            match_path = str(cfg.get("path") or "/")

        for k, v in (cfg.get("params") or {}).items():
            match_path = match_path.replace(f"%{k}", str(v)).replace(f":{k}", str(v))
        return match_path if match_path.startswith("/") else "/" + match_path

    async def _settle_render(self, timeout_ms: int = 0) -> None:
        """Wait for the client's render-lifecycle signal to leave 'busy' (zOS#97).

        zbifrost-client ≥1.7.114 stamps <html data-zrender="busy|idle"> from
        walk-send to last-chunk-painted — the SSOT that kills the chunk-stream
        race (asserts failing while the shot shows the value; not_contains
        passing on a page that hadn't painted YET). Waiting for "not busy"
        rather than == "idle" keeps older clients green: no attribute → settles
        immediately, exactly the pre-signal behavior. Best-effort by design —
        a timeout here never fails the step (the step's own selector waits and
        assertions still gate correctness; this only removes the race).
        """
        if self._page is None:
            return
        try:
            await self._page.wait_for_function(
                "() => document.documentElement.getAttribute('data-zrender') !== 'busy'",
                timeout=timeout_ms or self.timeout * 1000,
            )
        except Exception:  # pylint: disable=broad-except
            info("⚠ render-settle wait timed out (data-zrender stayed 'busy') — continuing")

    async def _run_open(self, route: Any) -> bool:
        await self._ensure_browser()
        base = self.http_url.rstrip("/")
        # $var route — open a URL lifted off the page by zCapture (zOS#98): the
        # "mint a share link, then OPEN it" leg that used to be hand-tested
        # forever. Unknown var fails loud, never navigates to the literal '$x'.
        if isinstance(route, str) and route.startswith("$"):
            captured = self._test_vars.get(route[1:])
            if captured is None:
                reason = f"zOpen {route!r} — no captured value (add a zCapture step first)"
                info(reason)
                self._last_response = {"event": "open_failed", "error": reason}
                return False
            route = str(captured)
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
        # zOS#97: the initial walk streams chunks after load — settle before
        # the content checks below read a half-painted page.
        await self._settle_render()

        # ── Bifrost content readiness ─────────────────────────────────────────
        # zbase.css is now a server-side <link> — synchronous with page load,
        # no async CDN fetch needed. We only wait for WS-rendered content.
        content_found = False
        ready_timeout_ms = int(self._raven_opts.get("content_ready_timeout", _BIFROST_READY_TIMEOUT_MS))
        try:
            await self._page.wait_for_selector(
                _BIFROST_CONTENT_SELECTOR, state="visible",
                timeout=ready_timeout_ms,
            )
            content_found = True
        except Exception:
            pass  # page has no dialogs/inputs — continue gracefully

        # ── Diagnostic console log + content gate ─────────────────────────────
        diag = None
        try:
            diag = await self._page.evaluate("""() => {
                const vaf    = document.querySelector('zVaF');
                const denial = Array.from(document.querySelectorAll('.zAlert-heading'))
                    .some(el => /access denied/i.test(el.textContent || ''));
                return {
                    zbaseLink:      !!document.querySelector('link[href*="zbase.css"]'),
                    zCanvas:        !!document.querySelector('link[href*="zCanvas.css"]'),
                    dashContainer:  !!document.querySelector('.zDash-container'),
                    contentVisible: !!document.querySelector('input[name], [data-dialog-id], .zDash-container'),
                    vafChildren:    vaf ? vaf.children.length : -1,
                    vafText:        vaf ? (vaf.innerText || '').trim().length : 0,
                    rbacDenied:     denial,
                    viewport:       `${window.innerWidth}x${window.innerHeight}`,
                };
            }""")
            parts = [f"viewport={diag['viewport']}"]
            if not diag['zbaseLink']:  parts.append("⚠ zbase.css link missing")
            if not diag['zCanvas']:    parts.append("⚠ zCanvas.css missing")
            if not diag['dashContainer']: parts.append("⚠ .zDash-container missing")
            if not diag['contentVisible']: parts.append("⚠ no content found")
            info(f"  page ready [{', '.join(parts)}]")
        except Exception:
            pass

        # ── Green-run honesty gate ────────────────────────────────────────────
        # A page that rendered an RBAC denial, or rendered NOTHING at all, must
        # fail the zOpen step — a screenshot of a blank/denied page is a false
        # positive. Opt out per-step (zOpen: {…, allow_empty: true}) or globally
        # (zRavenOptions.allow_empty_page: true) for intentionally bare pages.
        if diag:
            allow_empty = bool(
                (isinstance(route, dict) and route.get("allow_empty"))
                or self._raven_opts.get("allow_empty_page")
            )
            if diag["rbacDenied"]:
                reason = (f"zOpen {url} → page rendered an RBAC 'Access Denied' alert. "
                          f"Authenticate first (login steps before this zOpen) or open a public route.")
                info(f"✗ {reason}")
                self._last_response = {"event": "open_denied", "error": reason, "url": url}
                return False
            page_empty = (
                not diag["contentVisible"]
                and diag["vafChildren"] == 0
                and diag["vafText"] == 0
            )
            if page_empty and not allow_empty:
                reason = (f"zOpen {url} → page rendered no content "
                          f"(likely RBAC/auth denial or a broken route). "
                          f"Set allow_empty: true on this zOpen if a bare page is expected.")
                info(f"✗ {reason}")
                self._last_response = {"event": "open_empty", "error": reason, "url": url}
                return False
            # Redirect drift is informational — a login bounce lands elsewhere.
            final_path = self._page.url.replace(base, "", 1) or "/"
            wanted_path = url.replace(base, "", 1) or "/"
            if final_path.split("?")[0] != wanted_path.split("?")[0]:
                info(f"  ⚠ redirected: requested {wanted_path} but landed on {final_path}")

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
        # timestamp_shots: a mm-dd-HH-MM prefix on every shot filename, ON by
        # default — without it, a regenerated shot overwrites the prior one
        # in place under the identical name and an image viewer/IDE preview
        # never visually "kicks" (no diff to notice a re-run even happened).
        # Opt out per-run via zRavenOptions.timestamp_shots: false or
        # per-step shot.timestamp: false.
        use_ts      = cfg.get("timestamp", self._raven_opts.get("timestamp_shots", True))

        # Built-in settle: render-signal first (zOS#97 — a shot of a
        # mid-stream page is a false record), then sleep for explicit delay OR
        # default, then two rAF cycles so pending style recalc has painted.
        await self._settle_render()
        await asyncio.sleep((delay_ms or _SHOT_SETTLE_MS) / 1000)
        try:
            await self._page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
        except Exception:
            pass
        if resolution:
            await self._page.set_viewport_size({"width": int(resolution[0]), "height": int(resolution[1])})

        retain = cfg.get("retain", self._raven_opts.get("zshots_retain", 2))

        def _shot_path(base_dir: str, name: str, idx: int | None = None) -> str:
            ts_prefix = ""
            if use_ts or not overwrite:
                ts_prefix = _time.strftime("%m-%d-%H-%M") + "_"
            if idx is not None:
                filename = f"{ts_prefix}{name}_{idx}.{fmt}"
            else:
                filename = f"{ts_prefix}{name}.{fmt}"
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
            if use_ts and retain:
                _prune_old_shots(burst_dir, step_name, fmt, retain)
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
            if use_ts and retain:
                _prune_old_shots(shots_root, step_name, fmt, retain)

        self._last_response = {"event": "shot", "paths": saved}
        return True

    async def _capture_failure_shot(self, step_name: str) -> None:
        """Best-effort screenshot the instant a Bifrost step fails.

        A compound step (zOpen + zWait + zShot) aborts at the first failing
        primitive and never reaches its own zShot line — so without this, a
        failing zOpen (the most common failure) leaves zero visual evidence,
        which is exactly backwards: a failure is when you most need to SEE
        what the browser actually rendered. Never raises — a failed shot must
        not mask the original failure reason.
        """
        if not self._page:
            return
        try:
            raven_dir  = _os.path.dirname(_os.path.abspath(self._zraven_file)) if self._zraven_file else "zRaven"
            raven_name = _os.path.basename(self._zraven_file or "zRaven.unknown.zolo")
            raven_name = raven_name.removeprefix("zRaven.").removesuffix(".zolo")
            shots_root = _os.path.join(
                raven_dir, "zShots", raven_name,
                self._viewport_mode if self._viewport_mode else "",
            ).rstrip("/")
            _os.makedirs(shots_root, exist_ok=True)
            ts_prefix = _time.strftime("%m-%d-%H-%M") + "_"
            p = _os.path.join(shots_root, f"{ts_prefix}{step_name}_FAILED.png")
            await self._page.screenshot(path=p, full_page=True)
            _prune_old_shots(shots_root, f"{step_name}_FAILED", "png", self._raven_opts.get("zshots_retain", 2))
            info(f"zShot (failure) → {p}")
        except Exception:  # pylint: disable=broad-except
            pass

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

    async def _run_fill(self, fields: Any, step_key: str = "") -> bool:
        """zFill: declarative form fill — the SAME primitive as zCLI, translated
        to the rendered DOM instead of stdin prompts. Same zRaven step, same
        zUI field names, both modes — no selectors authored, no mode-specific
        test steps.

        For each field: locate `[name='<field>']` (rendered from the zDialog
        field's zConv/name key), set its value per input type, then — after
        the last field — click the enclosing form's Submit button. That last
        part mirrors the zCLI dialog's own implicit "last field -> submit"
        flow, so one zFill both fills AND submits, on both surfaces.
        """
        await self._ensure_browser()
        if not isinstance(fields, dict) or not fields:
            self._last_response = {"event": "fill_failed", "error": "zFill requires a {field: value} mapping"}
            return False

        last_selector = None
        for field, raw_value in fields.items():
            selector = f"[name='{field}']"
            value = self._resolve_value(raw_value, f"{step_key}.{field}" if step_key else "")
            shown = "***" if _looks_secret(field) else f"{value!r}"
            info(f"browser.fill → {selector} = {shown}")
            try:
                el = await self._page.wait_for_selector(selector, state="visible", timeout=self.timeout * 1000)
            except Exception:
                self._last_response = {
                    "event": "fill_failed",
                    "error": f"field '{field}' not found ({selector}) — is the dialog rendered?",
                }
                return False
            tag = (await el.evaluate("el => el.tagName")).lower()
            typ = (await el.get_attribute("type") or "").lower()
            if tag == "select":
                await el.select_option(str(value))
            elif typ == "checkbox":
                truthy = value if isinstance(value, bool) else str(value).strip().lower() in ("true", "1", "yes", "on")
                await el.set_checked(truthy)
            elif typ == "radio":
                await self._page.check(f"{selector}[value='{value}']")
            else:
                await el.fill(str(value))
            last_selector = selector

        # Implicit submit — same UX contract as the zCLI dialog's Enter-to-submit
        # default. A pure-collection dialog (no submit button) just no-ops here.
        if last_selector:
            try:
                clicked = await self._page.evaluate(
                    """(sel) => {
                        const el = document.querySelector(sel);
                        const form = el && el.closest('form');
                        const btn = form && form.querySelector("button[type='submit']");
                        if (btn) { btn.click(); return true; }
                        return false;
                    }""",
                    last_selector,
                )
                if clicked:
                    await asyncio.sleep(0.3)
            except Exception:  # pylint: disable=broad-except
                pass

        self._last_response = {"event": "filled", "fields": list(fields.keys())}
        return True

    async def _run_pick(self, option: Any) -> bool:
        """zPick: send a menu/action pick — the SAME primitive as zCLI, translated
        to a click on the rendered `button[data-zkey='<Option>']` (the zUI
        menu-item/action key — zbifrost-client stamps every rendered element
        with data-zkey, NOT data-key — now automated so the same zRaven step
        runs unmodified in both modes).

        A zDash panel pick is the SAME author-facing verb (16_dashboards.md's
        numbered menu in zCLI == a sidebar click in Bifrost) but a DIFFERENT
        widget under the hood: dashboard_renderer.js stamps `data-panel` on an
        `<a>` inside `.zDash-sidebar`, never `data-zkey` on a `<button>` — first
        exercised end-to-end by zDemos/zConsole. A comma-joined CSS selector
        matches whichever shape actually rendered, so one zRaven step keeps
        working across a plain menu AND a zDash sidebar without branching.
        """
        await self._ensure_browser()
        opt = str(option)
        selector = f"button[data-zkey='{opt}'], .zDash-sidebar [data-panel='{opt}']"
        info(f"browser.pick → {selector}")
        try:
            await self._page.click(selector, timeout=self.timeout * 1000)
        except Exception as exc:  # pylint: disable=broad-except
            self._last_response = {
                "event": "pick_failed",
                "error": f"option '{opt}' not found ({selector}): {exc}",
            }
            return False
        await asyncio.sleep(0.2)
        # zOS#97: a pick usually triggers a walk — settle so the next step
        # reads the picked page, not the previous one mid-repaint.
        await self._settle_render()
        self._last_response = {"event": "picked", "option": opt}
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
        await self._settle_render()  # zOS#97 — clicks can trigger a walk
        self._last_response = {"event": "clicked", "selector": selector}
        return True

    async def _run_wait(self, cfg: dict) -> bool:
        await self._ensure_browser()
        # zWait: zRender — the explicit form of the render-settle signal
        # (zOS#97): wait until the client reports the page finished painting.
        if isinstance(cfg, str) and cfg.strip().lower() == "zrender":
            info("browser.wait → zRender (page finished rendering)")
            await self._settle_render()
            self._last_response = {"event": "waited", "selector": "zRender"}
            return True
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

    async def _run_capture(self, cfg: dict, step_name: str = "zCapture") -> bool:
        """zCapture (Bifrost, zOS#98): lift a rendered value into a $var.

        The dual-mode sibling of zCLI's zCapture (regex over terminal output).
        A generated value the APP minted at runtime — share token, id, URL —
        can now drive later steps: `zOpen: $share_url`, `zFetch: {url: $api}`,
        `zFill: {code: $ref}`. Before this, that last leg ("open the GOOD
        link") was hand-tested forever.

        cfg:
          var:      share_url                 # stored as $share_url (required)
          selector: "[data-zkey='Link'] a"    # DOM read (waits for attached)
          property: href                      # innerText (default) | value |
                                              #   any attribute, then JS property
          pattern:  "token=(\\S+)"            # optional regex refine; group(1)
                                              #   if grouped, else whole match
        No selector → pattern regexes the whole page innerText (the Bifrost
        analog of the terminal buffer — the SAME {var, pattern} step runs in
        both modes). Settles on the render signal first (zOS#97): never
        captures off a half-painted page.
        """
        await self._ensure_browser()
        var      = str(cfg.get("var") or "").strip()
        selector = cfg.get("selector")
        pattern  = cfg.get("pattern")
        prop     = str(cfg.get("property", "innerText"))
        if not var or not (selector or pattern):
            self._last_response = {
                "event": "capture_failed",
                "error": "zCapture requires 'var' plus 'selector' (DOM read) "
                         "and/or 'pattern' (regex over page text)",
            }
            return False

        await self._settle_render()  # zOS#97 — the value must have painted

        if selector:
            sel = _strip_sel(str(selector))
            info(f"browser.capture → {sel} [{prop}]")
            try:
                # 'attached' not 'visible': hrefs/values on hidden inputs are
                # legitimate capture targets.
                el = await self._page.wait_for_selector(
                    sel, state="attached", timeout=self.timeout * 1000)
                raw = await el.evaluate(
                    """(el, prop) => {
                        if (prop === 'innerText') return el.innerText;
                        if (prop === 'value') return el.value ?? '';
                        const attr = el.getAttribute(prop);
                        if (attr !== null) return attr;
                        const v = el[prop];
                        return v == null ? '' : String(v);
                    }""",
                    prop,
                )
            except Exception as exc:  # pylint: disable=broad-except
                self._last_response = {
                    "event": "capture_failed",
                    "error": f"zCapture: element not found ({sel}): {exc}",
                }
                return False
        else:
            info(f"browser.capture → page text ~ /{pattern}/")
            raw = await self._page.evaluate(
                "() => document.body ? document.body.innerText : ''")

        value = str(raw or "").strip()
        if pattern:
            m = _re.search(str(pattern), value, _re.IGNORECASE | _re.MULTILINE)
            if not m:
                tail = value[-400:].strip() if len(value) > 400 else value
                self._last_response = {
                    "event": "capture_failed",
                    "error": f"zCapture: pattern {pattern!r} not found in "
                             f"captured text\n  Text was:\n{tail}",
                }
                return False
            value = m.group(1) if m.lastindex else m.group(0)

        self._test_vars[var] = value
        shown = "«masked»" if _looks_secret(var) else repr(value)
        info(f"captured ${var} = {shown}")
        self._last_response = {"event": "captured", "var": var, "value": value}
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
        # Nudge: let popstate → WS round-trip start, then settle on the render
        # signal (zOS#97) — an explicit zWait after this stays supported but is
        # no longer required for correctness.
        await asyncio.sleep(0.3)
        await self._settle_render()
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
        if key == "zFill":
            return await self._run_fill(val, step_key=step_name)
        if key == "zClean":
            return await self._run_clean(val)
        if key == "zClick":
            return await self._run_click(val)
        if key == "zPick":
            return await self._run_pick(val)
        if key == "zWait":
            return await self._run_wait(val)
        if key == "zCapture":
            return await self._run_capture(val, step_name)
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
                await self._capture_failure_shot(step_name)
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
            # zOS#97: never assert against a mid-stream page. The killer shape
            # this closes: a not_contains PASSING because the content hadn't
            # rendered YET — a green test on an incomplete page.
            if self._page is not None:
                await self._settle_render()
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
                await self._capture_failure_shot(step_name)
                self._record_fail(step_name, f"TIMEOUT — {exc}")
                ok = False
            except Exception as exc:  # pylint: disable=broad-except
                await self._capture_failure_shot(step_name)
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

        # zVaF.html is optional (zServer falls back to a built-in default — see
        # rendering/default_templates.py) but the fallback is easy to forget about
        # mid-project, so raven surfaces it loudly instead of leaving it to a
        # buried server-log INFO line.
        if app_dir and not (Path(app_dir) / "templates" / "zVaF.html").is_file():
            warn_step(
                "No templates/zVaF.html",
                "running on built-in default chrome — add one only if you need custom <head>/meta/fonts",
            )

        # If the parent runner (raven_command._handle_run) already isolated Data/,
        # it also owns the restore — and crucially does it AFTER server shutdown,
        # when the CSV adapter has flushed its in-memory tables. Restoring here
        # (pre-shutdown) would let that flush re-pollute the restored originals.
        _parent_isolated = bool(app_dir) and (Path(app_dir) / "Data._zraven_bak").exists()
        _isolated = prepare_test_data(app_dir) if app_dir else False
        if _isolated and not _parent_isolated:
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
            if _isolated and not _parent_isolated:
                teardown_test_data(app_dir)
                info(f"data restored: {app_dir}/Data/")

        self.print_summary()
        return self.failed == 0
