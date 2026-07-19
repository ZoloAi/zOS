"""
zDesktop — Native window launcher for zOS apps.

When zDesktop: true is set in zSpark, opens the app in a borderless
native WebView window (pywebview) instead of printing a browser URL.

macOS: WKWebView  |  Windows: WebView2/mshtml  |  Linux: gtk/qt

Usage in zSpark:
    title: My App
    zDesktop: true
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import zOS


def _run_window(url: str, title: str) -> None:
    """Open a native webview window blocking the calling thread."""
    try:
        import webview  # pywebview
    except ImportError:
        print(
            "\n[zDesktop] pywebview not installed. "
            "Run: pip install 'zolo-os[webview]'\n"
        )
        return

    webview.create_window(
        title,
        url,
        width=1200,
        height=800,
        resizable=True,
        frameless=False,
        easy_drag=False,
        min_size=(800, 600),
    )
    webview.start(debug=False)
    # When the user closes the window, signal shutdown back to the engine.
    # The import is deferred to avoid circular deps.
    try:
        from .engine import get_current_zos  # pylint: disable=import-outside-toplevel
        z = get_current_zos()
        if z is not None:
            z.shutdown()
    except Exception:  # pylint: disable=broad-except
        pass


def launch_desktop_window(zos: "zOS") -> None:
    """
    Open the native desktop window ON THE MAIN THREAD (pywebview requirement).

    The caller (engine.run) must move server.wait() to a background thread
    before calling this — this function blocks until the window is closed.
    """
    url = zos.server.get_url() if zos.server and zos.server.is_running() else "http://127.0.0.1:5000"
    title = zos.zspark_obj.get("title", "zOS App")

    print(f"\n[zDesktop] Opening native window → {url}\n")
    _run_window(url, title)
