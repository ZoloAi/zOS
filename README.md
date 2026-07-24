# zOS

> **Alpha — v1.6**
> zOS is stable and actively used in production internally. The API is functional and the architecture is settled, but rough edges remain. The `Documentation/` guides are technically accurate against the core design; some details may lag behind the latest source. Live, up-to-date docs are coming with the official alpha release via zCloud (zolo.media). Expect breaking changes before v2.0.
>
> Every release is gated on the full demo test matrix passing on **macOS, Linux, and Windows — arm64 and x86_64**.

---

## **Declare once—run everywhere.**

**zOS** is not just a Command Line Interface, but a **Context Layer Interface**—a declarative cross-platform **Python framework** where context flows through layers to determine how your application manifests.

Write once, adapt to any context: **user role**, **deployment environment**, **device**, or **runtime mode** (**Terminal** or **Web**). **zOS** handles the heavy lifting, turning ideas into working tools faster.

---

## Quick Start

**One-line install** (isolated venv at `~/.zolo`, CLI on your PATH):

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/ZoloAi/zOS/main/install.sh | bash
```

```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/ZoloAi/zOS/main/install.ps1 | iex
```

**Or plain pip** (Python 3.10–3.13):

```bash
pip install zolo-os
```

> **⚠️ The package name is [`zolo-os`](https://pypi.org/project/zolo-os/) — exactly that.**
> `pip install zolo` succeeds but installs an **unrelated squatted package** that has nothing to do with zOS. There is no `zolo-desktop` or `zos-desktop` either — the desktop/native-window mode is an extra of the same package: `pip install "zolo-os[webview]"`.

**Then run a demo:**

```bash
git clone https://github.com/ZoloAi/zOS.git
cd zOS/zDemos/zHello
z zSpark.zhello.zolo
```

---

## 📚 New to **Zolo**?

Start with **[The zPhilosophy](Documentation/zPhilosophy.md)**.  
It introduces the core concepts of **zOS** and smoothly leads into the layer-by-layer guides with ready-made demos.

### Requirements

- **CPython 3.10 – 3.13** (the range the zGuard trust binaries ship for)
- **macOS / Linux / Windows**, arm64 or x86_64

> Need help installing requirements on **Windows** or **macOS**?  
> See [**zInstall Guide**](Documentation/Setup/zInstall_GUIDE.md) for detailed instructions.

---

## Installation Options

| Variant | Use Case | Install Command |
|---------|----------|-----------------|
| **Basic** | CSV + SQLite backends | `pip install zolo-os` |
| **PostgreSQL** | + PostgreSQL backend | `pip install "zolo-os[postgresql]"` |
| **Webview** | + native desktop window mode (zDesktop) | `pip install "zolo-os[webview]"` |
| **Monitoring** | + Prometheus metrics | `pip install "zolo-os[monitoring]"` |
| **Full** | everything above | `pip install "zolo-os[all]"` |

> See [**zInstall Guide**](Documentation/Setup/zInstall_GUIDE.md) for editable install and troubleshooting.


---

## 🏗️ Architecture

**zOS v1.5+** (Context Layer Interface) follows a **5-layer architecture** inspired by "*Linux From Scratch*"—each subsystem stands alone, tested independently, then composed into higher abstractions.

```
Layer 0: /zSys/             — Pre-boot utilities: formatting, errors, install, logging, CLI routing
Layer 1: /L1_Foundation/    — zConfig (config hierarchy + secrets) + zComm (HTTP, WebSocket, services)
Layer 2: /L2_Handling/      — Display, Auth, Dispatch, Navigation, Parser, Loader (+ plugins), Func, Dialog, Open
Layer 3: /L3_Abstraction/   — zWizard (workflows), zData, zBifrost (WS bridge), zShell (REPL)
Layer 4: /L4_Orchestration/ — zWalker (declarative UI orchestrator) + zServer (HTTP/WSGI server)
```

### Subsystems by Layer

| Subsystem | Purpose |
|-----------|---------|
| | **Layer 1 — /L1_Foundation/** |
| **[zConfig](Documentation/zConfig_GUIDE.md)** | **Self-aware config layer** — **machine → environment → session** hierarchy with **secrets + logging** |
| **[zComm](Documentation/zComm_GUIDE.md)** | **Communication hub** — **HTTP client**, **service orchestration** (PostgreSQL, Redis), **network utilities** |
| | **Layer 2 — /L2_Handling/** |
| **[zDisplay](Documentation/zDisplay_GUIDE.md)** | **Render everywhere** — **30+ events** (tables, forms, widgets) adapt to **Terminal or GUI** automatically |
| **[zAuth](Documentation/L2_Handling/zAuth_GUIDE.md)** | **Three-tier auth system** — **bcrypt + RBAC + git-like identity**, manage **platform + multi-app users** simultaneously |
| **[zDispatch](Documentation/L2_Handling/zDispatch_GUIDE.md)** | **Universal command router** — **simple modifiers (^~*!)** shape behavior, routes to **7+ subsystems** seamlessly |
| **[zNavigation](Documentation/L2_Handling/zNavigation_GUIDE.md)** | **Unified navigation** — **menus + breadcrumbs + state + inter-file links**, all **RBAC-aware** |
| **[zParser](Documentation/zParser_GUIDE.md)** | **Declarative paths & parsing** — **workspace-relative + user dirs + plugin discovery**, 21+ unified methods |
| **[zLoader](Documentation/zLoader_GUIDE.md)** | **Intelligent file loader** — **4-tier cache system** (System + Pinned + Schema + Plugin) with **mtime tracking** |
| **[zFunc](Documentation/L2_Handling/zFunc_GUIDE.md)** | **Dynamic Python executor** — **cross-language** (using zBifrost) + **internal Python**, auto-injection removes boilerplate |
| **[zDialog](Documentation/L2_Handling/zDialog_GUIDE.md)** | **Declarative form engine** — **define once, auto-validate, render everywhere** (Terminal or GUI) |
| **[zOpen](Documentation/L2_Handling/zOpen_GUIDE.md)** | **Universal opener** — **cross-OS routing** (URLs, files, zPaths) for **your tools** (session-aware browser + IDE preferences) |
| | **Layer 3 — /L3_Abstraction/** |
| **~~zUtils~~** | **REMOVED v1.7.0** — Plugin management migrated to **zLoader** (Layer 1) - see [migration guide](Documentation/zUtils_GUIDE.md) |
| **[zWizard](Documentation/L3_Abstraction/zWizard_GUIDE.md)** | **Multi-step orchestrator** — **sequential execution + zHat result passing**, enabling workflows **and** navigation |
| **[zData](Documentation/L3_Abstraction/zData_GUIDE.md)** | **Database abstraction** — **backend-agnostic declarations** (SQLite ↔ PostgreSQL ↔ CSV), and **auto migration** |
| **[zBifrost](Documentation/L3_Abstraction/zBifrost_GUIDE.md)** | **WebSocket bridge** — **real-time bidirectional** communication (server + **JavaScript client**), enables **Terminal → Web GUI** transformation |
| **[zShell](Documentation/L3_Abstraction/zShell_GUIDE.md)** | **Interactive command center** — **18+ commands + wizard canvas**, persistent history, **direct access** to all subsystems |
| | **Layer 4 — /L4_Orchestration/** |
| **[zWalker](Documentation/L4_Orchestration/zWalker_GUIDE.md)** | **Declarative UI orchestrator** — **menus + breadcrumb navigation**, coordinates the lower-layer subsystems, Terminal **and** GUI |
| **[zServer](Documentation/L4_Orchestration/zServer_GUIDE.md)** | **HTTP/WSGI server** — **serves HTML/CSS/JS + declarative routing**, dev mode (lightweight) and production mode (**Gunicorn**), pairs with **zBifrost** |
| **[zRaven](Documentation/L4_Orchestration/README.md)** | **Automated test subsystem** — drives zWalker + zServer + zBifrost end-to-end; zSpark-activated, **off by default** |
| | [**L4 overview →**](Documentation/L4_Orchestration/README.md) |

## 🔒 Security & secrets

zOS treats environment files like `dotenv`: `zEnv.base.zolo` and `zEnv.<env>.zolo`
are parsed and injected into `os.environ` at boot — they are **never served over
HTTP**. The built-in `zServer` `SecurityChecker` returns `403` for:

- env/config/manifest files (`/zEnv.*`, `/zConfig.*`, `/zSpark.*`, `/certs/`, …)
- any hidden path segment (`/.git/`, `/.env`, …) — even nested under a mount
- source/secret file types served as assets (`.py`, `.zolo`, `.key`, `.pem`, `.db`, …)

So a `/plugins/` mount serves your client `.js`, but never the server-side `.py`.

**Production checklist**

- Keep `zEnv.*` and `certs/*.key|pem|cert` **gitignored** — never commit real secrets.
- Inject prod secrets via the platform (IAM role / secrets manager), not files.
- Set TLS certs in `zEnv.production` → HTTPS/WSS auto-enable (TLS 1.2+).
- Set the **public** `WEBSOCKET_HOST`/port and `WEBSOCKET_ALLOWED_ORIGINS`.

> **Alpha note:** WebSocket origin/CSRF validation is enabled together with
> `WEBSOCKET_REQUIRE_AUTH` (per-feature toggles land before v2.0) — set it in
> production. Token verification is constant-time (`hmac.compare_digest`).

---

## Uninstall & cleanup

Run this command in your terminal:

```bash
zolo uninstall
```
This launches an **interactive menu** where you can choose:

1. **Framework Only** (default) - Removes the package, keeps your data and optional dependencies
2. **Clean Uninstall** - Removes package AND all user data (configs, databases, cache)
3. **Dependencies Only** - Removes optional dependencies (pandas, psycopg2) but keeps zOS

Each option shows you exactly what will be removed and asks for confirmation before proceeding.

**[More details →](Documentation/Setup/zInstall_GUIDE.md#6-uninstall--cleanup)**


## License

MIT License with Ethical Use Clause

Copyright (c) 2024 Gal Nachshon

**Trademarks:** "Zolo" and "zOS" (Context Layer Interface) are trademarks of Gal Nachshon.

See [LICENSE](LICENSE) for details.

---

## Documentation

> The guides below are technically accurate against the core architecture, but some details may be slightly behind the current source. Live docs with full examples will ship with the official alpha at [zolo.media](https://zolo.media).

- **[zPhilosophy](Documentation/zPhilosophy.md)** - Core concepts and design principles
- **[Installation Guide](Documentation/Setup/zInstall_GUIDE.md)** - Setup instructions
- **[AI Agent Guide](Documentation/AI_AGENT_GUIDE.md)** - Reference for AI coding assistants
- **[Subsystem Guides](Documentation/)** - Guides for all 20+ subsystems

---

**[Next: The zPhilosophy →](Documentation/zPhilosophy.md)**
