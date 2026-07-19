// ZoloLauncher — the canonical zOS installer + desktop shell (zOS #33).
//
// The download IS the install. Jobs, in the order a fresh Mac meets them:
//   1. Engine missing: run the canonical installer (install.sh + z patch)
//      in a native progress window — no Terminal, no pasted commands.
//   2. Machine not signed in: open the user's zRM and BRIDGE the web sign-in
//      to the machine — an injected script asks zCloud for a one-time key
//      once the session is authenticated, and the launcher replays it via
//      `z login --token`. Signing into your zRM signs your Mac in. One act.
//   3. Double-clicked .zolo: hand the file to `z` with ZOS_DESKTOP=1
//      (the engine owns the app window; we exit).
//   4. Everything in place: the zRM in a native window — the control room.
//
// Product logic stays server-side (zRM) or in the engine (PyPI/z patch);
// this binary is a doorman and almost never needs a rebuild.

import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var installLog: NSTextView?
    private var openedFile = false
    private var handoffDone = false

    private static let homeURL = URL(string: "https://zolo.media/zAccount/zRM")!
    private static let helpURL = URL(string: "https://zolo.media/zStack/zOS/Foundations")!
    private static let installCmd =
        "curl -fsSL https://raw.githubusercontent.com/ZoloAi/zOS/main/install.sh | bash " +
        "&& \"$HOME/.zolo/venv/bin/z\" patch"

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        // application(_:open:) fires BEFORE didFinishLaunching on doc-open
        // launches — only run the main flow on a plain launch.
        if !openedFile {
            mainFlow()
        }
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls where url.pathExtension.lowercased() == "zolo" {
            openedFile = true
            if zBinary() == nil {
                // Install first, then launch the file the user asked for.
                runInstaller { ok in
                    if ok { self.launchZolo(file: url) } else { self.installFailed() }
                }
            } else {
                launchZolo(file: url)
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    // MARK: - the flow

    private func mainFlow() {
        if zBinary() == nil {
            runInstaller { ok in
                if ok { self.showWeb(url: Self.homeURL, bridge: true) }
                else  { self.installFailed() }
            }
        } else {
            showWeb(url: Self.homeURL, bridge: !machineSignedIn())
        }
    }

    private func zBinary() -> String? {
        // The two places the installer puts `z` — venv first (SSOT), then the
        // ~/.local/bin symlink.
        let home = NSHomeDirectory()
        return ["\(home)/.zolo/venv/bin/z", "\(home)/.local/bin/z"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private func machineSignedIn() -> Bool {
        // zOwnership at rest — the file `z login` writes (zguard zownership_store).
        let path = NSHomeDirectory() +
            "/Library/Application Support/zOS/zConfigs/zConfig.identity.zolo"
        guard let text = try? String(contentsOfFile: path, encoding: .utf8) else {
            return false
        }
        return text.contains("api_key:")
    }

    // MARK: - native install (no Terminal)

    private func runInstaller(then done: @escaping (Bool) -> Void) {
        let win = makeWindow(title: "Installing Zolo", width: 720, height: 460)

        let scroll = NSScrollView(frame: win.contentView!.bounds)
        scroll.autoresizingMask = [.width, .height]
        scroll.hasVerticalScroller = true

        let text = NSTextView(frame: scroll.bounds)
        text.isEditable = false
        text.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
        text.backgroundColor = NSColor(calibratedWhite: 0.07, alpha: 1)
        text.textColor = NSColor(calibratedWhite: 0.85, alpha: 1)
        text.autoresizingMask = [.width]
        scroll.documentView = text
        win.contentView?.addSubview(scroll)
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        installLog = text
        appendLog("→ Setting up Zolo on this Mac (a few minutes; nothing to do)…\n\n")

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/bash")
        proc.arguments = ["-c", Self.installCmd]
        // Finder launches with cwd=/ — z patch's `z agents` would then probe the
        // read-only system root (crashed pre-1.6.23 wheels; skips politely after).
        // Home is the honest workspace for a machine-level install either way.
        proc.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        var env = ProcessInfo.processInfo.environment
        // .app processes get a skeletal PATH; the installer expects a user one.
        env["PATH"] = "\(NSHomeDirectory())/.local/bin:/usr/local/bin:/opt/homebrew/bin:" +
                      (env["PATH"] ?? "/usr/bin:/bin")
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] fh in
            let data = fh.availableData
            guard !data.isEmpty, let chunk = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async { self?.appendLog(chunk) }
        }
        proc.terminationHandler = { [weak self] p in
            pipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                let ok = p.terminationStatus == 0 && self?.zBinary() != nil
                self?.appendLog(ok ? "\n✓ Zolo is installed.\n" : "\n✗ Install failed.\n")
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { done(ok) }
            }
        }
        do { try proc.run() } catch {
            appendLog("✗ Couldn't start the installer: \(error.localizedDescription)\n")
            done(false)
        }
    }

    private func appendLog(_ chunk: String) {
        guard let text = installLog else { return }
        text.textStorage?.append(NSAttributedString(
            string: chunk,
            attributes: [.font: NSFont.monospacedSystemFont(ofSize: 12, weight: .regular),
                         .foregroundColor: NSColor(calibratedWhite: 0.85, alpha: 1)]))
        text.scrollToEndOfDocument(nil)
    }

    private func installFailed() {
        let alert = NSAlert()
        alert.messageText = "Zolo couldn't finish installing"
        alert.informativeText =
            "Your Mac is fine — nothing was changed. Check your internet connection " +
            "and open Zolo again, or visit zolo.media/zStack/zOS/Foundations for help."
        alert.addButton(withTitle: "Open the help page")
        alert.addButton(withTitle: "Quit")
        if alert.runModal() == .alertFirstButtonReturn {
            NSWorkspace.shared.open(Self.helpURL)
        }
        NSApp.terminate(nil)
    }

    // MARK: - the .zolo handoff

    private func launchZolo(file: URL) {
        guard let z = zBinary() else {
            showWeb(url: Self.helpURL, bridge: false)
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

    // MARK: - the web window (zRM) + the sign-in bridge

    // Injected only while the machine has no zOwnership: once the web session
    // is signed in, ask zCloud's desktop door for a one-time key and post it
    // to the launcher. Quiet until then — 401s just mean "not signed in yet".
    private static let bridgeJS = """
    (function () {
      if (window.__zoloHandoff) { return; }
      window.__zoloHandoff = true;
      var done = false;
      function attempt() {
        if (done) { return; }
        fetch('/api/zdesktop/handoff', {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-Zolo-Desktop': '1' }
        }).then(function (r) { return r.ok ? r.json() : null; })
          .then(function (j) {
            var key = j && j.data && j.data.api_key;
            if (key && !done) {
              done = true;
              window.webkit.messageHandlers.zoloDesktop.postMessage(key);
            } else if (!done) {
              setTimeout(attempt, 3000);
            }
          })
          .catch(function () { setTimeout(attempt, 3000); });
      }
      attempt();
    })();
    """

    private func showWeb(url: URL, bridge: Bool) {
        window?.close()
        let win = makeWindow(title: "Zolo", width: 1200, height: 800)
        win.minSize = NSSize(width: 800, height: 600)

        let config = WKWebViewConfiguration()
        if bridge {
            let controller = WKUserContentController()
            controller.add(self, name: "zoloDesktop")
            controller.addUserScript(WKUserScript(
                source: Self.bridgeJS,
                injectionTime: .atDocumentEnd,
                forMainFrameOnly: true))
            config.userContentController = controller
        }

        let wv = WKWebView(frame: win.contentView!.bounds, configuration: config)
        wv.autoresizingMask = [.width, .height]
        wv.customUserAgent = (wv.value(forKey: "userAgent") as? String ?? "Mozilla/5.0")
            + " ZoloDesktop/1.0"
        wv.load(URLRequest(url: url))
        win.contentView?.addSubview(wv)
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        window = win
        webView = wv
    }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        guard message.name == "zoloDesktop", !handoffDone,
              let key = message.body as? String, !key.isEmpty,
              let z = zBinary() else { return }
        handoffDone = true

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: z)
        proc.arguments = ["login", "--token", key]
        proc.terminationHandler = { p in
            DispatchQueue.main.async {
                if p.terminationStatus == 0 {
                    // Machine signed in — say it once, quietly, and move on.
                    let note = NSAlert()
                    note.messageText = "This Mac is signed in to Zolo"
                    note.informativeText =
                        "Your apps and your account now work together on this machine."
                    note.addButton(withTitle: "Great")
                    note.runModal()
                } else {
                    self.handoffDone = false   // let the bridge try again next sign-in
                }
            }
        }
        try? proc.run()
    }

    private func makeWindow(title: String, width: CGFloat, height: CGFloat) -> NSWindow {
        let win = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        win.title = title
        win.center()
        win.isReleasedWhenClosed = false
        return win
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
