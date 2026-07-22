// Zolo.exe — the canonical zOS installer + desktop shell for Windows.
// The 1:1 twin of desktop/macos/ZoloLauncher.swift; same doctrine, same flows:
//
//   1. Engine missing: run the canonical installer (install.ps1 + z patch)
//      in a native progress window — no Terminal, no pasted commands.
//   2. Machine not signed in: open the user's zRM and BRIDGE the web sign-in
//      to the machine — injected script asks /api/zdesktop/handoff for a
//      one-time key once the session is authenticated; we replay it via
//      `z login --token`. Signing into your zRM signs your PC in. One act.
//   3. Double-clicked .zolo (argv[0]): hand the file to `z` with
//      ZOS_DESKTOP=1 (the engine owns the app window; we exit).
//   4. Everything in place: the zRM in a native WebView2 window.
//
// Product logic stays server-side (zRM) or in the engine (PyPI/z patch);
// this binary is a doorman and almost never needs a rebuild.

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.WinForms;

namespace Zolo
{
    internal static class Program
    {
        private const string HomeUrl = "https://zolo.media/zAccount/zRM";
        private const string HelpUrl = "https://zolo.media/zStack/zOS/Foundations";
        private const string InstallCmd =
            "irm https://raw.githubusercontent.com/ZoloAi/zOS/main/install.ps1 | iex; " +
            "& \"$env:USERPROFILE\\.zolo\\venv\\Scripts\\z.exe\" patch";

        // Injected only while the machine has no zOwnership (mirror of the
        // Swift bridgeJS — WebView2 speaks chrome.webview instead of webkit).
        private const string BridgeJs = @"
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
                      window.chrome.webview.postMessage(key);
                    } else if (!done) {
                      setTimeout(attempt, 3000);
                    }
                  })
                  .catch(function () { setTimeout(attempt, 3000); });
              }
              attempt();
            })();";

        private static bool _handoffDone;

        [STAThread]
        private static void Main(string[] args)
        {
            ApplicationConfiguration.Initialize();

            var zoloFile = args.Length > 0 && args[0].EndsWith(".zolo", StringComparison.OrdinalIgnoreCase)
                ? args[0] : null;

            if (ZBinary() == null)
            {
                RunInstaller(ok =>
                {
                    if (!ok) { InstallFailed(); return; }
                    if (zoloFile != null) LaunchZolo(zoloFile);
                    else ShowWeb(HomeUrl, bridge: true);
                });
            }
            else if (zoloFile != null)
            {
                LaunchZolo(zoloFile);
                return;   // engine owns the window; the doorman exits
            }
            else
            {
                ShowWeb(HomeUrl, bridge: !MachineSignedIn());
            }

            Application.Run();
        }

        // ── engine + ownership probes ────────────────────────────────────────

        private static string? ZBinary()
        {
            var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            var z = Path.Combine(home, ".zolo", "venv", "Scripts", "z.exe");
            return File.Exists(z) ? z : null;
        }

        private static bool MachineSignedIn()
        {
            // zOwnership at rest — the file `z login` writes (zguard
            // zownership_store): platformdirs user_data_dir("zOS", "zolo").
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var path = Path.Combine(local, "zolo", "zOS", "zConfigs", "zConfig.identity.zolo");
            try { return File.Exists(path) && File.ReadAllText(path).Contains("api_key:"); }
            catch { return false; }
        }

        // ── native install (no Terminal) ─────────────────────────────────────

        private static void RunInstaller(Action<bool> done)
        {
            var win = MakeWindow("Installing Zolo", 720, 460);
            var log = new TextBox
            {
                Multiline = true, ReadOnly = true, Dock = DockStyle.Fill,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.FromArgb(18, 18, 18), ForeColor = Color.Gainsboro,
                Font = new Font("Consolas", 10),
            };
            win.Controls.Add(log);
            win.Show();
            Append(log, "-> Setting up Zolo on this PC (a few minutes; nothing to do)...\r\n\r\n");

            // Absolute path + neutral CWD (first field trial, urina's PC):
            // a bare "powershell.exe" resolves through PATH — hijackable and,
            // worse, AV/policy layers judge the spawn by its full story. The
            // canonical System32 path with %TEMP% as CWD is the least alarming
            // shape an unsigned exe can ask for. Sysnative dodges the WOW64
            // System32->SysWOW64 redirect if the launcher ever runs 32-bit.
            var sys32 = Environment.GetFolderPath(Environment.SpecialFolder.System);
            var ps = Path.Combine(sys32, "WindowsPowerShell", "v1.0", "powershell.exe");
            if (!File.Exists(ps))
                ps = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                                  "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe");
            var proc = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = File.Exists(ps) ? ps : "powershell.exe",
                    Arguments = "-NoProfile -ExecutionPolicy Bypass -Command \"" + InstallCmd + "\"",
                    WorkingDirectory = Path.GetTempPath(),
                    UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardOutput = true, RedirectStandardError = true,
                },
                EnableRaisingEvents = true,
            };
            proc.OutputDataReceived += (_, e) => { if (e.Data != null) Append(log, e.Data + "\r\n"); };
            proc.ErrorDataReceived  += (_, e) => { if (e.Data != null) Append(log, e.Data + "\r\n"); };
            proc.Exited += (_, _) => win.BeginInvoke(() =>
            {
                var ok = proc.ExitCode == 0 && ZBinary() != null;
                Append(log, ok ? "\r\n[ok] Zolo is installed.\r\n" : "\r\n[x] Install failed.\r\n");
                var t = new System.Windows.Forms.Timer { Interval = 1200 };
                t.Tick += (_, _) => { t.Stop(); win.Close(); done(ok); };
                t.Start();
            });

            try
            {
                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
            }
            catch (Exception ex)
            {
                Append(log, "[x] Couldn't start the installer: " + ex.Message + "\r\n");
                Append(log, "[!] This usually means antivirus or a security policy blocked " +
                            "PowerShell. Add an exception for Zolo (or pause the antivirus), " +
                            "then open Zolo again.\r\n");
                done(false);
            }
        }

        private static void Append(TextBox log, string chunk)
        {
            if (log.IsDisposed) return;
            if (log.InvokeRequired) { log.BeginInvoke(() => Append(log, chunk)); return; }
            log.AppendText(chunk);
        }

        private static void InstallFailed()
        {
            var pick = MessageBox.Show(
                "Your PC is fine — nothing was changed. Check your internet connection and " +
                "open Zolo again, or visit zolo.media/zStack/zOS/Foundations for help.\n\n" +
                "Open the help page now?",
                "Zolo couldn't finish installing",
                MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
            if (pick == DialogResult.Yes)
                Process.Start(new ProcessStartInfo(HelpUrl) { UseShellExecute = true });
            Application.Exit();
        }

        // ── the .zolo handoff ────────────────────────────────────────────────

        private static void LaunchZolo(string file)
        {
            var z = ZBinary();
            if (z == null) { ShowWeb(HelpUrl, bridge: false); return; }
            var psi = new ProcessStartInfo
            {
                FileName = z,
                Arguments = "\"" + Path.GetFileName(file) + "\"",
                WorkingDirectory = Path.GetDirectoryName(Path.GetFullPath(file)) ?? ".",
                UseShellExecute = false,
            };
            psi.Environment["ZOS_DESKTOP"] = "1";   // engine opens the native window
            try { Process.Start(psi); } catch { /* engine reports its own errors */ }
        }

        // ── the web window (zRM) + the sign-in bridge ────────────────────────

        private static async void ShowWeb(string url, bool bridge)
        {
            var win = MakeWindow("Zolo", 1200, 800);
            win.MinimumSize = new Size(800, 600);
            var wv = new WebView2 { Dock = DockStyle.Fill };
            win.Controls.Add(wv);
            win.Show();

            await wv.EnsureCoreWebView2Async();
            wv.CoreWebView2.Settings.UserAgent += " ZoloDesktop/1.0";
            if (bridge)
            {
                await wv.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(BridgeJs);
                wv.CoreWebView2.WebMessageReceived += (_, e) =>
                    OnHandoffKey(e.TryGetWebMessageAsString());
            }
            wv.CoreWebView2.Navigate(url);
        }

        private static void OnHandoffKey(string? key)
        {
            if (_handoffDone || string.IsNullOrWhiteSpace(key)) return;
            var z = ZBinary();
            if (z == null) return;
            _handoffDone = true;

            Task.Run(() =>
            {
                var proc = Process.Start(new ProcessStartInfo
                {
                    FileName = z, Arguments = "login --token " + key,
                    UseShellExecute = false, CreateNoWindow = true,
                });
                proc?.WaitForExit();
                if (proc?.ExitCode == 0)
                {
                    MessageBox.Show(
                        "Your apps and your account now work together on this machine.",
                        "This PC is signed in to Zolo",
                        MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                else
                {
                    _handoffDone = false;   // let the bridge try again next sign-in
                }
            });
        }

        private static Form MakeWindow(string title, int width, int height) => new()
        {
            Text = title,
            Width = width, Height = height,
            StartPosition = FormStartPosition.CenterScreen,
            Icon = LoadIcon(),
        };

        private static Icon? LoadIcon()
        {
            try { return Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch { return null; }
        }
    }
}
