// ZoloLauncher — the thin macOS shell (zOS #33).
//
// Deliberately contains NO product logic. Three jobs only:
//   1. Default open (no file): the user's zRM in a native window — the
//      desktop control room. Admin stays web-only by design.
//   2. Double-clicked .zolo: hand the file to the installed `z` CLI with
//      ZOS_DESKTOP=1 (the engine owns the app window; we exit).
//   3. Engine missing: show the Foundations install page — the front door.
//
// Everything that can change lives server-side (zRM) or in the engine
// (updatable via PyPI/z patch) — so this binary almost never needs a rebuild.

import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var openedFile = false

    private static let homeURL = URL(string: "https://zolo.media/zAccount/zRM")!
    private static let installURL = URL(string: "https://zolo.media/zStack/zOS/Foundations")!

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        // application(_:open:) fires BEFORE didFinishLaunching on doc-open
        // launches — only fall back to the zRM window on a plain launch.
        if !openedFile {
            showWeb(url: Self.homeURL)
        }
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls where url.pathExtension.lowercased() == "zolo" {
            openedFile = true
            launchZolo(file: url)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    // MARK: - the .zolo handoff

    private func zBinary() -> String? {
        // The two places the one-liner installer puts `z` — venv first (SSOT),
        // then the ~/.local/bin symlink.
        let home = NSHomeDirectory()
        return ["\(home)/.zolo/venv/bin/z", "\(home)/.local/bin/z"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private func launchZolo(file: URL) {
        guard let z = zBinary() else {
            showWeb(url: Self.installURL)
            return
        }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: z)
        proc.arguments = [file.lastPathComponent]
        proc.currentDirectoryURL = file.deletingLastPathComponent()
        var env = ProcessInfo.processInfo.environment
        env["ZOS_DESKTOP"] = "1"   // engine opens the native window (zOS engine seam)
        proc.environment = env
        do {
            try proc.run()
            // The engine owns the window from here; the launcher's job is done.
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                NSApp.terminate(nil)
            }
        } catch {
            showAlertThenQuit("Couldn't start zOS: \(error.localizedDescription)")
        }
    }

    // MARK: - the web window (zRM / install page)

    private func showWeb(url: URL) {
        let rect = NSRect(x: 0, y: 0, width: 1200, height: 800)
        let win = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        win.title = "Zolo"
        win.minSize = NSSize(width: 800, height: 600)
        win.center()
        win.isReleasedWhenClosed = false

        let wv = WKWebView(frame: rect)
        wv.autoresizingMask = [.width, .height]
        wv.load(URLRequest(url: url))
        win.contentView = wv
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        window = win
        webView = wv
    }

    private func showAlertThenQuit(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Zolo"
        alert.informativeText = message
        alert.runModal()
        NSApp.terminate(nil)
    }

    // MARK: - minimal menu (Cmd+Q / Cmd+W / Cmd+C&V in the webview)

    private func buildMenu() {
        let main = NSMenu()

        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Zolo",
                        action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let editItem = NSMenuItem()
        main.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All",
                         action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = editMenu

        let windowItem = NSMenuItem()
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Close Window",
                           action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        windowMenu.addItem(withTitle: "Minimize",
                           action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowItem.submenu = windowMenu

        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
