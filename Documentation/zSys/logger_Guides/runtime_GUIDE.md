# zSys Logger — Runtime Guide

> **Modules:** `core/zSys/logger/console.py`, `execution_context.py`
> **Purpose:** Logging in contexts where the full zCLI logger isn't available — standalone **WSGI workers** (`ConsoleLogger`) — plus the small **execution-context** diagnostic that records *how* the process was launched.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**

---

## `ConsoleLogger` (`console.py`)

A lightweight logger for processes that run **outside** a full `zCLI` instance — primarily WSGI workers, where the framework logger isn't accessible. It produces the **same canonical line** as everything else by routing through `format_log_message`, but without the stdlib `logging` machinery (no handlers, no levels, no propagation) — just `print` to stdout.

```python
from zSys.logger import ConsoleLogger

logger = ConsoleLogger(context="WSGI")
logger.info("Server started on port %d", 8000)
logger.error("Connection failed: %s", err)
```

| Method | Level | Notes |
|--------|-------|-------|
| `.debug` / `.info` / `.warning` / `.error` / `.critical` | matching level string | `%`-style args (`msg % args`) when args are passed |

Internally each call funnels through `_log(level, msg, *args)`:

```python
def _log(self, level, msg, *args):
    if args:
        msg = msg % args
    print(format_log_message(
        timestamp=datetime.now(), level=level,
        context=self.context, message=msg, include_details=False,
    ))
```

- **Console-only** — no file logging, no `SESSION` level (the worker context doesn't need it).
- **Format parity** — because it uses `format_log_message`, WSGI worker output is visually identical to Bootstrap/Framework/App lines (see [formats_GUIDE](formats_GUIDE.md)).

> **Why a separate logger?** A WSGI worker may be a forked/imported process without the `zCLI` singleton. `ConsoleLogger` keeps its dependency surface to `datetime` + `format_log_message`, so it's safe to construct anywhere.

---

## `log_execution_context` (`execution_context.py`)

A single diagnostic helper that records **how** the process was invoked — useful when reading a bootstrap log after the fact.

```python
def log_execution_context(logger, args, python_file, zspark_file):
    verbose  = getattr(args, "verbose", False)
    dev_mode = getattr(args, "dev", False)
    if zspark_file:
        exec_type = "zSpark"
    elif python_file:
        exec_type = f"python ({python_file})"
    else:
        exec_type = f"command ({getattr(args, 'command', None) or 'info'})"
    logger.debug("Execution: %s, Verbose: %s, Dev: %s", exec_type, verbose, dev_mode)
```

It classifies the launch into one of three execution types — **zSpark**, **python (file)**, or **command** — and logs it (plus the `--verbose`/`--dev` flags) at `DEBUG` against whatever logger is passed (typically the `BootstrapLogger`). Defensive `getattr` access means a partial/odd `args` namespace can't crash the diagnostic.

---

## Trust notes

- **No exec / no network / no file write.** `ConsoleLogger` prints to stdout; `log_execution_context` logs one `DEBUG` line.
- **Foreign content is data** — `ConsoleLogger` interpolates via `%`-args; `log_execution_context` only reads attribute values and formats them as a string.
- **Defensive reads** — `getattr(args, …, default)` keeps the execution-context diagnostic from throwing on an incomplete args object.

**[← Back to Logger Guide](../logger_GUIDE.md) | [Home](../../../README.md)**
