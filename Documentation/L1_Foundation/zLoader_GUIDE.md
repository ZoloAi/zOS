**[← Back to zComm Guide](zComm_GUIDE.md) | [Home](../../README.md) | [Next: zFunc Guide →](../L2_Handling/zFunc_GUIDE.md)**

---

# zLoader

**zLoader** is a **Layer 1 subsystem** initialized by **zOS** (Position 6).
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

It provides intelligent file loading with multi-tier caching, format detection, automatic invalidation, and plugin management - through one unified interface.

You get:

- **Zero configuration**  
- **No manual file handling**
- **No cache management**  
- **Intelligent multi-tier caching** (system, pinned, schema, python modules)
- **Automatic format detection** (.zolo, .yaml, .json)
- **Mtime invalidation** (auto-reload on file changes)
- **zParser integration** (path resolution and content parsing)
- **Session-aware loading** (fallback to session context)
- **Plugin management** (Python/JavaScript module loading with collision detection)

## Architecture Overview

**zLoader** is composed of specialized modules organized in a 6-tier architecture with cache modules in a dedicated subdirectory:

| Tier | Module | Purpose | Guide |
|------|--------|---------|-------|
| **Tier 1** | **loader_io** | Raw file I/O operations | [io_GUIDE.md](zLoader_Guides/io_GUIDE.md) |
| **Tier 2** | **cache/cache_system** | System cache (UI/config with LRU eviction) | [cache_system_GUIDE.md](zLoader_Guides/cache_system_GUIDE.md) |
| **Tier 2** | **cache/cache_pinned** | Pinned cache (user aliases, no eviction) | [cache_pinned_GUIDE.md](zLoader_Guides/cache_pinned_GUIDE.md) |
| **Tier 2** | **cache/cache_schema** | Schema cache (DB connections + transactions) | [cache_schema_GUIDE.md](zLoader_Guides/cache_schema_GUIDE.md) |
| **Tier 2** | **cache/cache_python_module** | Python module cache (collision detection + auto-reload) | [cache_plugin_GUIDE.md](zLoader_Guides/cache_plugin_GUIDE.md) |
| **Tier 3** | **cache/cache_orchestrator** | Unified cache router (delegates to Tier 2) | [orchestrator_GUIDE.md](zLoader_Guides/orchestrator_GUIDE.md) |
| **Tier 4** | **loader_modules/__init__** | Package aggregator (public API exposure) | *(internal)* |
| **Tier 5** | **zLoader.py** | Main facade (public interface to zOS) | *(this guide)* |
| **Tier 6** | **__init__.py** | Package root (zLoader entry point) | *(internal)* |
| **Tier 0** | **loader_constants** | Shared constants + exception hierarchy | [constants_GUIDE.md](zLoader_Guides/constants_GUIDE.md) |
| **Support** | **loader_validator** | Fail-fast config/path/type validation | [validator_GUIDE.md](zLoader_Guides/validator_GUIDE.md) |
| **Support** | **loader_trust** | Plugin-trust gate (zGuard seam) | [trust_GUIDE.md](zLoader_Guides/trust_GUIDE.md) |
| **Support** | **cache/cache_utils** | Cache inspection utilities | [utils_GUIDE.md](zLoader_Guides/utils_GUIDE.md) |
| **Support** | **cache/cache_pattern** | Wildcard matcher (SSOT for all caches) | [pattern_GUIDE.md](zLoader_Guides/pattern_GUIDE.md) |

**Reorganized Structure (v1.7.0+):** All cache implementations live in the `cache/` subdirectory. The `cache_python_module` tier caches dynamically loaded code, gated by the `loader_trust` plugin-trust seam before execution.

This guide provides a **facade overview** of zLoader. For deep dives into specific modules, see the guides in `zLoader_Guides/`.

---

## What's in This Guide

This guide covers the **main zLoader facade** - the unified interface to all file loading and caching features. Following the zConfig/zComm pattern, we focus on:

1. **Architecture Overview** - 6-tier structure and design patterns
2. **Initialization** - How zLoader auto-initializes after zParser
3. **Tutorials** - Hands-on demos (Level 0-4) for learning by doing
4. **API Reference** - Complete method signatures and usage patterns
5. **Advanced Features** - Multi-tier caching, format detection, session integration

**What's NOT in this guide:**
- Deep dives into individual cache tiers (see `zLoader_Guides/` folder)
- Path resolution internals (see [zParser Guide](../L2_Handling/zParser_GUIDE.md))
- Content parsing logic (see [zParser Guide](../L2_Handling/zParser_GUIDE.md))

**Current Implementation Status:**
- ✅ System Cache (UI/config files with LRU eviction)
- ✅ Pinned Cache (User aliases with no eviction)
- ✅ Schema Cache (DB connections + transactions)
- ✅ PythonModule Cache (Module instances + collision detection + auto-reload)
- ✅ Cache Orchestrator (Unified routing to all tiers)
- ✅ Format Detection (.zolo, .yaml, .json auto-detection)
- ✅ Mtime Invalidation (Auto-reload on file changes)
- ✅ zParser Integration (Path resolution and parsing delegation)

---

## Initialization Order

When you call `zOS()`, zLoader initializes automatically after zParser:

1. **zConfig Ready** - Configuration subsystem initialized
2. **zComm Ready** - Communication subsystem initialized
3. **zParser Ready** - Path resolution and parsing ready
4. **zLoader Initialization** - File loading subsystem starts:
   - Validate zOS instance (session + logger required)
   - Create CacheOrchestrator (manages all 4 cache tiers)
   - Initialize System Cache (UI/config with LRU eviction)
   - Initialize Pinned Cache (user aliases, no eviction)
   - Initialize Schema Cache (DB connections + transactions)
   - Initialize PythonModule Cache (module instances + collision detection + auto-reload)
   - Store zParser method references (path resolution, file identification, content parsing)
   - Print ready message (Layer 1, after zDisplay)
   - Log ready state
5. **zLoader Ready** - File loading infrastructure available

This order ensures zLoader has access to configuration (from zConfig), path resolution (from zParser), and logging (from zLogger) before initializing the cache system.

**Auto-Initialization:**
```python
from zOS import zOS

z = zOS()  # zConfig → zComm → zParser → zLoader → other subsystems

# zLoader is now ready:
ui_data = z.loader.handle("@.zUI.users.zolo")          # Load UI file
config = z.loader.handle("~.zConfig.app.zolo")         # Load config file
schema = z.loader.handle("@.zSchema.users.zolo")       # Load schema (fresh)
z.loader.load_plugins(["/path/to/my_plugin.py"])       # Load plugin module(s)
plugin = z.loader.get_plugin("my_plugin")              # Access loaded plugin
```

---

## Tutorials

**Learn by doing!** 

The tutorials below are organized in a bottom-up fashion. Every tutorial below has a working demo you can run and modify.

**A Note on Learning zOS:**  
Each tutorial (lvl1, lvl2, lvl3...) progressively introduces more complex features of **this subsystem**. The early tutorials start with familiar imperative patterns (think Django-style conventions) to meet you where you are as a developer.

As you progress through zOS's subsystems, you'll notice a gradual shift from imperative to declarative patterns. This intentional journey helps reshape your mental model from imperative to declarative thinking. Only when you reach **Layer 3 (Orchestration)** will you see subsystems used **fully declaratively** as intended in production. By then, the true magic of declarative coding will reveal itself, and you'll understand why we started this way.

Get the demos:

```bash
# Clone only the Demos folder
git clone --depth 1 --filter=blob:none --sparse https://github.com/ZoloAi/zolo-zcli.git
cd zolo-zcli
git sparse-checkout set Demos
```

> All zLoader demos are in: `Demos/Layer_1/zLoader_Demo/`

---

# **zLoader - Level 0** (Hello zLoader)

After mastering zParser's path resolution and content parsing, you're ready to explore zLoader - zOS's intelligent file loading layer with multi-tier caching.

**The same zSpark pattern** from zConfig demos unlocks zLoader's capabilities:

```python
from zOS import zOS

# Familiar zSpark pattern from zConfig
zSpark = {
    "deployment": "Development",  # Show subsystem banners
    "title": "hello-loader",      # Session identifier
    "logger": "INFO",              # Console + file logging
    "logger_path": "./logs",       # Where logs go
}

# Watch the initialization order in the output:
# [zConfig Ready] → [zComm Ready] → [zParser Ready] → [zLoader Ready]

z = zOS(zSpark)

# zLoader is now ready to use!
```

**Key Discovery**: zLoader auto-initializes immediately after zParser when you call `zOS()`. It's a Layer 1 subsystem - built on top of Layer 0 (zConfig, zComm) and Layer 0.5 (zParser).

**🎯 Try it yourself:**

Run the demo to see zLoader in action:

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl0_hello/1_hello_loader.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl0_hello/1_hello_loader.py)

**What you'll discover:**
- Watch the initialization order: [zConfig Ready] → [zComm Ready] → [zParser Ready] → [zLoader Ready]
- zLoader is Layer 1 (built on zParser)
- Same zSpark pattern as previous subsystems
- File loading infrastructure ready with zero configuration

---

# **zLoader - Level 1** (Basic File Loading)

### **i. Load UI File**

In Level 0, you watched zLoader initialize. Now let's actually **use** it.  
The simplest zLoader action? Loading a UI file.

**What are zVaFiles?** zVaFiles are zOS's declarative file format for UI definitions, schemas, and configurations. They can be written in three formats:
- **.zolo** - Native zOS format (preferred)
- **.yaml** - YAML format (human-readable)
- **.json** - JSON format (machine-readable)

zLoader automatically detects the format and delegates parsing to zParser.

**UI files** define user interfaces declaratively - menus, forms, workflows, etc. zLoader loads and caches them for instant reuse.

Let's load a UI file:

```python
from zOS import zOS

# Consistent zSpark pattern
zSpark = {
    "deployment": "Production",
    "title": "ui-load",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Load UI file from workspace
# "@." prefix means "workspace-relative"
ui_data = z.loader.handle("@.zUI.users.zolo")

# Access parsed data
print(f"UI Name: {ui_data['zName']}")
print(f"Blocks: {list(ui_data.keys())}")
```

> One line to load and parse. No manual file handling. Format auto-detected. Cache managed automatically.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl1_basic/1_load_ui.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl1_basic/1_load_ui.py)

**What you'll discover:**
- Load UI files with one method call
- zPath notation: "@." (workspace), "~." (absolute)
- Format auto-detection (.zolo, .yaml, .json)
- Automatic caching (second load is instant)
- Parsed data returned as Python dict

---

### **ii. Load Config File**

Now that you've loaded a UI file, let's load a **config file**. Config files define application settings, environment variables, and deployment configurations.

```python
from zOS import zOS

# Consistent zSpark pattern
zSpark = {
    "deployment": "Production",
    "title": "config-load",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Load config file
# "~." prefix means "absolute path" (system-wide config)
config_data = z.loader.handle("~.zConfig.app.zolo")

# Access settings
print(f"App Name: {config_data.get('app_name')}")
print(f"Version: {config_data.get('version')}")
```

> Same interface as UI loading. zLoader handles both identically.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl1_basic/2_load_config.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl1_basic/2_load_config.py)

**What you'll discover:**
- Load config files with same interface
- System-wide configs via "~." prefix
- Automatic caching (like UI files)
- Same format auto-detection

---

### **iii. Load Schema File (Fresh)**

You've loaded UI and config files (both cached). Now let's load a **schema file** - but with a twist!

**Schema files** define database structures (tables, fields, constraints). Unlike UI/config files, **schemas are NEVER cached** - they're always loaded fresh to reflect the latest DB structure.

```python
from zOS import zOS

# Consistent zSpark pattern
zSpark = {
    "deployment": "Production",
    "title": "schema-load",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Load schema file
# Note: Schemas are ALWAYS loaded fresh (not cached)
schema_data = z.loader.handle("@.zSchema.users.zolo")

# Access schema structure
print(f"Tables: {list(schema_data.get('tables', {}).keys())}")
print(f"Fields: {len(schema_data.get('fields', []))}")
```

> Schemas bypass cache - always fresh data. zLoader detects "zSchema" in filename and skips caching automatically.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl1_basic/3_load_schema.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl1_basic/3_load_schema.py)

**What you'll discover:**
- Schemas are NEVER cached (by design)
- Fresh data on every load
- Auto-detection via "zSchema" in filename
- Same loading interface as UI/config

---

**🎯 Level 1 Complete!**

You've learned the core file loading fundamentals:
- ✅ **Load UI File** - Cached for instant reuse
- ✅ **Load Config File** - Cached like UI files
- ✅ **Load Schema File** - Always fresh (not cached)

**These are the essentials. Most applications only need these.**

---

# **zLoader - Level 2** (Intelligent Caching)

> **Note:** Throughout Level 2, we're exploring caching **imperatively** - understanding the mechanics. This is Layer 1 basics. Later, you'll see caching used **declaratively** with full automation. We're starting with the foundation!

Remember Level 1 where loading was instant on the second call? That's zLoader's **intelligent multi-tier caching** at work. Let's understand how it works.

### **i. Cache Hit vs Miss**

Every time you load a file, zLoader follows a **3-priority fallback**:
1. **Priority 1: Cache** - Instant lookup (microseconds)
2. **Priority 2: Fresh Load** - File I/O (milliseconds)
3. **Priority 3: Parse** - Content parsing (milliseconds)

Let's see this in action:

```python
from zOS import zOS
import time

zSpark = {
    "deployment": "Production",
    "title": "cache-hit",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# First load - cache miss (disk I/O + parsing)
start = time.time()
ui_data1 = z.loader.handle("@.zUI.users.zolo")
time1 = time.time() - start

# Second load - cache hit (instant)
start = time.time()
ui_data2 = z.loader.handle("@.zUI.users.zolo")
time2 = time.time() - start

print(f"First load: {time1*1000:.2f}ms (disk I/O + parsing)")
print(f"Second load: {time2*1000:.2f}ms (cache hit)")
print(f"Speedup: {time1/time2:.0f}x faster")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl2_caching/1_cache_hit.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl2_caching/1_cache_hit.py)

**What you'll discover:**
- First load: ~5-10ms (disk I/O + parsing)
- Second load: ~0.01ms (cache hit)
- 100-1000x speedup on cached loads
- Automatic cache management (no manual keys)

---

### **ii. Mtime Invalidation**

Cache hits are great, but what happens when the file **changes**? zLoader uses **mtime (modification time) invalidation** to detect changes and reload automatically.

```python
from zOS import zOS
import os
import time

zSpark = {
    "deployment": "Production",
    "title": "mtime-invalidation",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Load file (cache miss)
ui_data1 = z.loader.handle("@.zUI.test.zolo")
print("First load: cache miss")

# Load again (cache hit)
ui_data2 = z.loader.handle("@.zUI.test.zolo")
print("Second load: cache hit")

# Simulate file change (touch file to update mtime)
file_path = os.path.join(z.session['zSpace'], 'zUI.test.zolo')
os.utime(file_path, None)  # Update modification time
time.sleep(0.1)  # Ensure mtime difference

# Load again (cache invalidated - fresh load)
ui_data3 = z.loader.handle("@.zUI.test.zolo")
print("Third load: cache invalidated (file changed)")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl2_caching/2_mtime_invalidation.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl2_caching/2_mtime_invalidation.py)

**What you'll discover:**
- Automatic mtime detection on every load
- Cache invalidation when file changes
- Fresh reload without manual cache clearing
- Zero stale data issues

---

### **iii. Multi-Tier Cache Strategy**

zLoader uses **4 independent cache tiers**, each optimized for different use cases:

| Tier | Name | Purpose | Eviction | Max Size | Features |
|------|------|---------|----------|----------|----------|
| **1** | **System** | UI/config files | LRU | 100 | Mtime invalidation |
| **2** | **Pinned** | User aliases | None | Unlimited | User-controlled |
| **3** | **Schema** | DB connections | None | Per-session | Fresh loads |
| **4** | **PythonModule** | Python modules | LRU | 50 | Collision detection + auto-reload |

Let's see all tiers in action:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "multi-tier",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Tier 1: System Cache (UI/config files)
ui_data = z.loader.handle("@.zUI.users.zolo")
print("[Tier 1] System Cache: UI file loaded and cached")

# Tier 2: Pinned Cache (user aliases via zLoad command)
# Note: Pinned cache is accessed via zDispatch/zCLI, not directly
print("[Tier 2] Pinned Cache: User aliases (no eviction)")

# Tier 3: Schema Cache (DB connections)
# Note: Schema cache is managed by zData subsystem
print("[Tier 3] Schema Cache: DB connections (session-based)")

# Tier 4: PythonModule Cache (module instances)
z.loader.load_plugins(["/path/to/my_plugin.py"])
plugin = z.loader.get_plugin("my_plugin")
print("[Tier 4] PythonModule Cache: Module instance loaded and cached")

# Get stats from all tiers
stats = z.loader.cache.get_stats("all")
print(f"\nCache Stats: {stats}")
```

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl2_caching/3_multi_tier.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl2_caching/3_multi_tier.py)

**What you'll discover:**
- 4 independent cache tiers
- Each tier optimized for different use cases
- System cache: UI/config (LRU eviction)
- Pinned cache: User aliases (no eviction)
- Schema cache: DB connections (session-based)
- PythonModule cache: Python modules (collision detection + auto-reload)

---

**🎯 Level 2 Complete!**

You've mastered intelligent caching:
- ✅ **Cache Hit/Miss** - 100-1000x speedup on cached loads
- ✅ **Mtime Invalidation** - Auto-reload on file changes
- ✅ **Multi-Tier Strategy** - 4 independent cache tiers

**This is smart infrastructure - the cache works for you.** As you progress through zOS, you'll see how this caching enables declarative patterns!

---

# **zLoader - Level 3** (Advanced Features)

### **i. Session-Based Loading**

So far, you've loaded files explicitly via zPath (`"@.zUI.users.zolo"`). But zLoader also supports **session-based loading** - loading from session context when zPath is None.

**What is session context?** When navigating through zOS (zCLI, zWalker, zWizard), the session stores current UI context:
- `zVaFile`: Current UI filename
- `zVaFolder`: Current folder path
- `zMode`: Execution mode

zLoader can use these values as fallback when you don't specify a zPath.

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "session-load",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Set session context (normally done by zDispatch/zNavigation)
z.session['zVaFile'] = 'users.zolo'
z.session['zVaFolder'] = '@'  # Workspace-relative

# Load from session (zPath=None)
ui_data = z.loader.handle()  # No zPath argument!

print(f"Loaded from session: {ui_data['zName']}")
```

> Session-based loading enables navigation workflows - "load current UI" without explicit paths.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl3_advanced/1_session_load.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl3_advanced/1_session_load.py)

**What you'll discover:**
- Load from session context (zPath=None)
- Enables navigation workflows
- Uses session values: zVaFile, zVaFolder
- Fallback mechanism for implicit loading

---

### **ii. Absolute Path Loading**

You've used zPath notation (`"@.zUI.users.zolo"`) for workspace-relative paths. But some subsystems work with **absolute OS paths** directly (e.g., zServer route auto-detection).

zLoader supports absolute path loading via `handle_absolute_path()`:

```python
from zOS import zOS
import os

zSpark = {
    "deployment": "Production",
    "title": "absolute-load",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Build absolute path
workspace = z.session['zSpace']
abs_path = os.path.join(workspace, 'zUI.users.zolo')

# Load by absolute path (bypasses zPath decoder)
ui_data = z.loader.handle_absolute_path(abs_path)

print(f"Loaded via absolute path: {ui_data['zName']}")
```

> Absolute path loading bypasses zPath decoder but maintains same caching and format detection.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl3_advanced/2_absolute_path.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl3_advanced/2_absolute_path.py)

**What you'll discover:**
- Load files by absolute OS path
- Bypasses zPath notation (no "@." or "~.")
- Same caching and format detection
- Used by zServer for route auto-detection

---

### **iii. Format Detection**

zLoader automatically detects file formats, but you can **explicitly test** format detection:

```python
from zOS import zOS

zSpark = {
    "deployment": "Production",
    "title": "format-detect",
    "logger": "INFO",
    "logger_path": "./logs",
}
z = zOS(zSpark)

# Test format detection for different extensions
test_files = [
    "@.zUI.users.zolo",   # Native zOS format
    "@.zUI.users.yaml",   # YAML format
    "@.zUI.users.json",   # JSON format
]

for zPath in test_files:
    # zLoader delegates to zParser for format detection
    ui_data = z.loader.handle(zPath)
    print(f"{zPath}: Parsed successfully")
```

**Format Detection Priority:**
1. **.zolo** - Native zOS format (tried first)
2. **.json** - JSON format (tried second)
3. **.yaml** - YAML format (tried third)
4. **.yml** - YAML format (tried last)

> zLoader tries formats in order until one succeeds. First match wins.

**🎯 Try it yourself:**

```bash
python3 Demos/Layer_1/zLoader_Demo/lvl3_advanced/3_format_detection.py
```

[View demo source →](../Demos/Layer_1/zLoader_Demo/lvl3_advanced/3_format_detection.py)

**What you'll discover:**
- Automatic format detection (.zolo, .yaml, .json)
- Priority order: .zolo → .json → .yaml → .yml
- First match wins
- Delegation to zParser for actual detection

---

**🎯 Level 3 Complete!**

You've mastered advanced features:
- ✅ **Session-Based Loading** - Load from session context
- ✅ **Absolute Path Loading** - Direct OS path loading
- ✅ **Format Detection** - Auto-detect .zolo, .yaml, .json

**These features enable navigation workflows and subsystem integration.**

---

# **zLoader - Level 4** (Integration & Use Cases)

### **Real-World Integration - zDispatch**

Time to put everything together! Let's see how **zDispatch** uses zLoader for command dispatch and modifier resolution.

**The problem it solves:**  
When you run a command in zCLI mode, zDispatch needs to load the UI file, parse commands, and execute them. zLoader handles all file loading, caching, and format detection.

**The integration:**

```python
# In zDispatch (dispatch_launcher.py, line 447)
def launch_command(self, zVaFile):
    """Launch command from UI file."""
    # Load UI file via zLoader (cached after first load)
    raw_zFile = self.zos.loader.handle(zVaFile)
    
    # Process commands
    self._process_commands(raw_zFile)

# In zDispatch (dispatch_modifiers.py, line 570)
def resolve_modifier(self, zVaFile):
    """Resolve modifier from UI file."""
    # Load UI file via zLoader (cached if already loaded)
    raw_zFile = self.zos.loader.handle(zVaFile)
    
    # Extract modifier
    return self._extract_modifier(raw_zFile)
```

**Why this works:**
- **First load**: Disk I/O + parsing (~5-10ms)
- **Subsequent loads**: Cache hit (~0.01ms)
- **File changes**: Mtime invalidation (auto-reload)
- **Format changes**: Auto-detection (.zolo, .yaml, .json)

> zDispatch calls `loader.handle()` multiple times per session. Without caching, this would be 100-1000x slower!

**🎯 Try it yourself:**

Run a zCLI command to see zLoader integration:

```bash
# This command loads a UI file via zLoader
python3 -m zOS.zCLI users

# Watch the logs to see cache hits
cat ~/Library/Application\ Support/zOS/logs/zcli.log
```

**What you'll discover:**
- zDispatch uses zLoader for all file operations
- First command: Cache miss (disk I/O)
- Subsequent commands: Cache hit (instant)
- File changes: Auto-reload
- Zero manual cache management

---

### **Real-World Integration - zNavigation**

Now let's see how **zNavigation** uses zLoader for UI linking and navigation workflows.

**The problem it solves:**  
When you click a zLink in a UI (e.g., `{Settings: "@.zUI.settings.zolo"}`), zNavigation needs to load the target UI file. zLoader handles the loading, caching, and format detection.

**The integration:**

```python
# In zNavigation (navigation_linking.py)
def resolve_link(self, link_expr):
    """Resolve zLink expression to target UI."""
    # Parse link expression
    target_file = self._parse_link(link_expr)
    
    # Load target UI via zLoader (cached if already visited)
    target_ui = walker.loader.handle(target_file)
    
    # Navigate to target
    self._navigate_to(target_ui)
```

**Why this works:**
- **First visit**: Disk I/O + parsing (~5-10ms)
- **Return visits**: Cache hit (~0.01ms)
- **UI updates**: Mtime invalidation (auto-reload)
- **Navigation speed**: Instant (no disk I/O)

> zNavigation enables "instant" navigation between UIs. Without caching, every link click would require disk I/O!

**🎯 Try it yourself:**

Navigate between UIs to see zLoader integration:

```bash
# Start zCLI with UI navigation
python3 -m zOS.zCLI users

# Navigate to settings (first visit - cache miss)
# Type: settings

# Navigate back to users (cache hit)
# Type: users

# Navigate to settings again (cache hit)
# Type: settings
```

**What you'll discover:**
- zNavigation uses zLoader for all UI loading
- First visit: Cache miss (disk I/O)
- Return visits: Cache hit (instant)
- Navigation feels instant (no loading delays)
- Zero manual cache management

---

**🎯 Level 4 Complete!**

You've completed the entire zLoader tutorial journey:
- ✅ **Level 0**: Hello zLoader (Initialize zOS)
- ✅ **Level 1**: Basic file loading (UI, config, schema)
- ✅ **Level 2**: Intelligent caching (hit/miss, mtime invalidation, multi-tier)
- ✅ **Level 3**: Advanced features (session loading, absolute paths, format detection)
- ✅ **Level 4**: Real-world integration (zDispatch, zNavigation)

**You now understand the complete zLoader subsystem for intelligent file loading!**

---

## Module Structure

zLoader follows a 6-tier architecture with cache modules organized in a dedicated subdirectory:

```
L1_Foundation/c_zLoader/
├── zLoader.py                          (Tier 5 - Facade)
├── __init__.py                         (Tier 6 - Package Root)
└── loader_modules/
    ├── __init__.py                     (Tier 4 - Package Aggregator)
    ├── loader_io.py                    (Tier 1 - Foundation I/O)
    ├── loader_constants.py             (Tier 0 - Constants + exceptions)
    ├── loader_validator.py             (Support - Validation)
    ├── loader_trust.py                 (Support - Plugin-trust gate / zGuard seam)
    └── cache/                          (Tier 2-3 - Caching Layer)
        ├── __init__.py                 (Cache package exports)
        ├── cache_orchestrator.py       (Tier 3 - Unified router)
        ├── cache_system.py             (Tier 2 - UI/config cache)
        ├── cache_pinned.py             (Tier 2 - User aliases)
        ├── cache_schema.py             (Tier 2 - DB connections)
        ├── cache_python_module.py      (Tier 2 - Python/JS modules)
        ├── cache_pattern.py            (Support - Wildcard matcher SSOT)
        └── cache_utils.py              (Support - Cache inspection utilities)
```

**Tier 1 - Foundation:**
- `loader_io.py` - Raw file I/O operations

**Tier 2 - Cache Implementations (cache/ subdirectory):**
- `cache/cache_system.py` - System cache (UI/config with LRU eviction)
- `cache/cache_pinned.py` - Pinned cache (user aliases, no eviction)
- `cache/cache_schema.py` - Schema cache (DB connections + transactions)
- `cache/cache_python_module.py` - Python module cache (collision detection + auto-reload)

**Tier 3 - Cache Orchestrator (cache/ subdirectory):**
- `cache/cache_orchestrator.py` - Unified cache router (delegates to Tier 2)

**Tier 4 - Package Aggregator:**
- `loader_modules/__init__.py` - Public API exposure

**Tier 5 - Facade:**
- `zLoader.py` - Main facade class providing unified interface

**Tier 6 - Package Root:**
- `__init__.py` - Package exports and public API

**Tier 0 - Constants:**
- `loader_constants.py` - Shared constants + exception hierarchy (`LoaderError`, `CacheError`, `FileLoadError`, `ValidationError`, `PluginTrustError`)

**Support Modules:**
- `loader_validator.py` - Fail-fast validation (cache config, file paths, cache types, session structure)
- `loader_trust.py` - Plugin-trust gate (zGuard enforcement seam; permissive in open-core)
- `cache/cache_pattern.py` - `matches_pattern()` wildcard matcher (SSOT shared by all caches)
- `cache/cache_utils.py` - Cache inspection utilities (`get_cached_files`, etc.)

**Architecture Pattern:**
zLoader uses the **Facade pattern** with **Orchestrator delegation**:
- `z.loader.handle()` → `zLoader.handle()` → `CacheOrchestrator.get()` → `SystemCache.get()`
- Unified interface (`zLoader` class) delegates to orchestrator (`CacheOrchestrator`)
- Orchestrator routes to specialized cache tiers (`SystemCache`, `PinnedCache`, etc.)

This separation allows each tier to be tested and evolved independently while maintaining a stable public API.

---

## Layer 1 Design Philosophy

As a **Layer 1 subsystem**, zLoader has special design considerations:

**Depends on Layer 0:**
- Uses zConfig for configuration (logger, session)
- Uses zParser for path resolution and content parsing
- Initialized after Layer 0 subsystems ready

**Provides for Layer 2+:**
- File loading infrastructure for all subsystems
- Intelligent caching for performance
- Format detection for flexibility
- Used by zDispatch, zNavigation, zData, zWalker, zWizard, etc.

**Integration Points:**
- **Depends on:** zConfig (configuration), zParser (path resolution, parsing), zLogger (logging)
- **Used by:** zDispatch (command dispatch), zNavigation (UI linking), zData (schema loading), zWalker (UI traversal), zWizard (wizard flows), zServer (route auto-detection), zUtils (plugin loading)
- **Provides for:** 
  - File loading: Load UI, config, schema files
  - Intelligent caching: Multi-tier caching with mtime invalidation
  - Python module management: Collision detection, auto-reload, session injection (v1.7.0+)
  - Format detection: Auto-detect .zolo, .yaml, .json
  - Session integration: Load from session context

**Cache Consolidation (v1.7.0):**  
All Python module caching (plugins, functions) is now centralized in `zLoader`'s `PythonModuleCache`. This consolidation:
- Establishes `zLoader` as the Single Source of Truth (SSOT) for all caching
- Eliminates duplicate collision detection and mtime tracking logic from other subsystems
- Provides unified auto-reload functionality via `check_and_reload_all()`
- Reduces architectural redundancy and improves maintainability

---

## Advanced Features

### Cache Statistics

Get detailed statistics from all cache tiers:

`get_stats()` returns a dict **keyed by tier name** (`system_cache`, `pinned_cache`, `schema_cache`, `plugin_cache`) — not a flattened total. Each tier's value is that tier's own stats dict.

```python
# Get stats from all tiers
stats = z.loader.cache.get_stats("all")
print(stats["system_cache"]["hit_rate"])    # e.g. "83.3%"
print(stats["plugin_cache"]["collisions"])   # plugin collision count

# Get stats from a specific tier (still tier-keyed)
system = z.loader.cache.get_stats("system")["system_cache"]
print(f"System cache size: {system['size']}/{system['max_size']}")
```

**Per-tier stats shapes:**
- **system_cache / plugin_cache**: `hits`, `misses`, `hit_rate` (string `"NN.N%"`), `size`, `max_size`, `evictions`, `invalidations` (plugin also: `loads`, `collisions`)
- **pinned_cache**: `namespace`, `size`, `aliases`
- **schema_cache**: `namespace`, `active_connections`, `connections`

For cache-inspection helpers, see [utils_GUIDE.md](zLoader_Guides/utils_GUIDE.md).

---

### Cache Clearing

Clear cache manually when needed:

```python
# Clear all cache tiers
z.loader.cache.clear("all")

# Clear specific tier
z.loader.cache.clear("system")  # UI/config cache
z.loader.cache.clear("pinned")  # User aliases
z.loader.cache.clear("schema")  # DB connections
z.loader.cache.clear("plugin")  # Python module instances (uses PythonModuleCache)
```

**When to clear:**
- Development: Clear stale caches
- Testing: Reset cache state
- Memory management: Free unused cache entries
- Production: Rarely needed (mtime invalidation handles most cases)

---

### Plugin Management (Migrated from zUtils v1.7.0)

zLoader now provides plugin management functionality, eliminating the need for a separate zUtils subsystem:

```python
# Load plugins at boot time (via zSpark)
z = zOS({"plugins": ["/path/to/calculator.py", "/path/to/utils.js"]})

# Runtime loading
plugins = z.loader.load_plugins(["/path/to/plugin.py"])

# Access plugin module
calculator = z.loader.get_plugin("calculator")
result = calculator.add(5, 3)

# List all plugins
all_plugins = z.loader.get_plugins_dict()
plugin_info = z.loader.list_plugins()  # With metadata

# Execute via zFunc (declarative)
result = z.zfunc.handle("&calculator.add(5, 3)")
```

**Supported Plugin Types:**
- **Python plugins** (.py files or module import paths)
- **JavaScript plugins** (.js files - executed via zFunc)

**Features:**
- Collision detection (prevents duplicate plugin names)
- Auto-reload on file changes (mtime tracking)
- Session injection (`zos` instance injected automatically)
- Best-effort loading (failed plugins don't halt initialization)
- Progress display during batch loading
- **Plugin-trust gate** (see below) — runs before any plugin code executes

**Plugin Trust (zGuard seam):**

Loading a plugin executes arbitrary code (`importlib.exec_module` for `.py`, a Node subprocess for `.js`). Before that happens, `PythonModuleCache` calls the trust gate in `loader_trust.verify_plugin_trust(file_path, zos, logger)`:

- **Open-core (no zGuard):** the gate is a permissive no-op — any path loads. zOS stays fully functional out of the box.
- **With zGuard installed:** enforcement is sealed in the `zguard.loader.plugin_trust` binary wheel (allowed directories / signature checks). A denied path raises `PluginTrustError`, which propagates unwrapped so the denial is visible (never silently swallowed).

No call-site changes are needed to enable enforcement — installing zGuard seals the same seam. See [trust_GUIDE.md](zLoader_Guides/trust_GUIDE.md).

**Migration from zUtils:**
- `z.utils.load_plugins()` → `z.loader.load_plugins()`
- `z.utils.my_function()` → `z.loader.get_plugin("plugin").my_function()`
- `z.utils.plugins` → `z.loader.get_plugins_dict()`
- `z.utils.get_stats()` → `z.loader.cache.get_stats("plugin")["plugin_cache"]`

---

### Python Module Auto-Reload

The PythonModuleCache provides active auto-reload for all cached Python modules:

```python
# Proactively check all modules and reload if changed
reloaded = z.loader.cache.python_module_cache.check_and_reload_all()

if reloaded:
    print(f"Reloaded modules: {', '.join(reloaded)}")
else:
    print("All modules up-to-date")
```

**Auto-Reload Modes:**
- **Passive (automatic)**: Checks mtime when module is accessed via `get()`
- **Active (explicit)**: Checks all modules via `check_and_reload_all()`

**Use Cases:**
- Plugin systems that need periodic update checks
- Development environments with hot-reload requirements
- Systems exposing a "reload all plugins" command

**Performance:**
- Only calls `os.path.getmtime()` for each module (fast)
- Only reloads modules with changed mtimes
- Returns list of reloaded module names

---

### Facade API Reference

The `zLoader` class provides these convenience methods:

**File Loading:**
```python
# Load file by zPath
ui_data = z.loader.handle("@.zUI.users.zolo")
config_data = z.loader.handle("~.zConfig.app.zolo")
schema_data = z.loader.handle("@.zSchema.users.zolo")  # Fresh load (not cached)

# Load file by absolute path
abs_path = "/workspace/zUI.users.zolo"
ui_data = z.loader.handle_absolute_path(abs_path)

# Load from session context
z.session['zVaFile'] = 'users.zolo'
z.session['zVaFolder'] = '@'
ui_data = z.loader.handle()  # No zPath argument
```

**Cache Operations:**
```python
# Access cache orchestrator
cache = z.loader.cache

# Get from cache
data = cache.get("parsed:/path/to/file.zolo", cache_type="system", filepath="/path/to/file.zolo")

# Set in cache
cache.set("parsed:/path/to/file.zolo", data, cache_type="system", filepath="/path/to/file.zolo")

# Check cache
has_data = cache.has("parsed:/path/to/file.zolo", cache_type="system")

# Clear cache
cache.clear("all")  # All tiers
cache.clear("system")  # Specific tier

# Get stats
stats = cache.get_stats("all")  # All tiers
system_stats = cache.get_stats("system")  # Specific tier
```

**Direct Module Access:**
```python
# Access modules directly
z.loader.cache              # CacheOrchestrator instance
z.loader.display            # zDisplay reference
z.loader.logger             # zLogger reference
z.loader.zSession           # Session dictionary reference
```

---

## What's Next?

You've mastered **zLoader** (Layer 1 file loading and plugin management). Now continue to **zFunc** - function execution with auto-injection and declarative syntax:

**→ Continue to [zFunc Guide](../L2_Handling/zFunc_GUIDE.md)**

Layer 1 provides foundation utilities:
- **zLoader** - File loading, caching, and plugin management ← You are here
- **zFunc** - Function execution and plugin invocation

**Note**: The zUtils subsystem has been removed in v1.7.0. Plugin management is now part of zLoader. See [zUtils_GUIDE.md](../zUtils_GUIDE.md) for migration guide.

---

**[← Back to zComm Guide](zComm_GUIDE.md) | [Home](../../README.md) | [Next: zFunc Guide →](../L2_Handling/zFunc_GUIDE.md)**
