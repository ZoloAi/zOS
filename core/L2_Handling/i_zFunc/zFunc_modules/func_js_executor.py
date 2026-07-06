# zOS/core/L2_Handling/i_zFunc/zFunc_modules/func_js_executor.py

"""
JavaScript Function Execution Utilities.

This module provides the capability to execute JavaScript functions from external
.js files using Node.js, enabling cross-language function execution in zFunc.

Architecture Position
--------------------
**Tier 1: Foundation** - Extension for JavaScript function execution

This module extends the zFunc subsystem to support JavaScript alongside Python,
allowing zOS applications to call Node.js functions seamlessly.

Key Functionality
-----------------
- Execute JavaScript functions via Node.js subprocess
- JSON-based argument passing and result parsing
- Automatic Node.js detection and validation
- Comprehensive error handling for subprocess execution
- Support for CommonJS and ES6 module formats

Security Considerations
-----------------------
⚠️ **IMPORTANT**: This module executes arbitrary JavaScript files via Node.js.

**Trust gate**: Before spawning Node, ``execute_js_function`` calls
``verify_plugin_trust(file_path, zos, logger)`` — the same zGuard seam that gates
Python plugin loading in c_zLoader. Open-core: permissive no-op. With zGuard
installed the seam is sealed (allowed dirs / signature checks) and raises
``PluginTrustError`` on denial (code never executes — fails closed).

**Injection-safe invocation**: ``module_path``, ``func_name`` and ``args`` are
passed to the Node wrapper as a single JSON payload via an environment variable,
never string-interpolated into the script. This prevents JS injection through a
crafted file path or function name.

Integration Points
------------------
**Used By**:
- func_resolver.py: Calls execute_js_function() for .js files

**Dependencies**:
- subprocess: Node.js process execution
- json: Argument serialization and result parsing

Usage Examples
--------------
Example 1: Basic JavaScript function call
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>> result = execute_js_function(
    ...     "/path/to/math.js",
    ...     "add",
    ...     [5, 3],
    ...     logger
    ... )
    >>> print(result)  # Output: 8

Example 2: Error handling
    >>> try:
    ...     result = execute_js_function("/path/to/script.js", "func", [arg1], logger)
    ... except FileNotFoundError:
    ...     print("Node.js not found")
    ... except subprocess.CalledProcessError as e:
    ...     print(f"JavaScript execution failed: {e}")
"""

from zOS import os, json, subprocess, Any, List, Optional

# Messages + timeout drawn from the subsystem SSOT (func_constants).
from .func_constants import (
    TIMEOUT_JS_EXECUTION,
    DEBUG_MSG_JS_CALL,
    DEBUG_MSG_JS_RESULT,
    DEBUG_MSG_NODE_VERSION,
    ERROR_MSG_NODE_NOT_FOUND,
    ERROR_MSG_JS_FILE_NOT_FOUND,
    ERROR_MSG_JS_EXECUTION_FAILED,
    ERROR_MSG_JS_RESULT_PARSE,
    ERROR_MSG_JS_FUNCTION_NOT_FOUND,
    JS_BROWSER_GLOBALS,
    JS_NOT_DEFINED_SUFFIX,
)


class BrowserOnlyFunctionError(RuntimeError):
    """
    Raised when a ``.js`` zFunc fails because it touches a browser-only global
    (``document``, ``window`, …) that does not exist in a Node subprocess.

    A ``.js`` zFunc always runs server-side (Node) on BOTH zCLI and zBifrost, so
    this is never a surface mismatch — it means DOM/UI code was placed in a
    ``zFunc`` instead of a ``zScripts`` browser plugin. The zFunc facade catches
    this and renders one clean, render-agnostic warning signal (no traceback).
    """

    def __init__(self, func_name: str, global_name: str, file_path: str):
        self.func_name = func_name
        self.global_name = global_name
        self.file_path = file_path
        super().__init__(
            f"Browser-only function '{func_name}' uses '{global_name}' "
            f"(undefined in Node) in {file_path}"
        )


def _extract_error_json(stderr: str) -> Optional[dict]:
    """
    Pull the wrapper's single-line ``{__error__: …}`` payload out of ``stderr``.

    ``stderr`` is NOT guaranteed to be pure JSON: Node prints its own diagnostics
    there too (e.g. the "To load an ES module…" notice emitted when a ``.js``
    browser plugin is imported as a data: URL). ``json.loads(stderr)`` on the whole
    blob would therefore ``JSONDecodeError`` and we'd lose the structured error —
    in particular the browser-global classification. Scan lines instead and return
    the last one that parses to a dict carrying ``__error__``.
    """
    if not stderr:
        return None
    for line in reversed(stderr.strip().splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("__error__"):
            return data
    return None


def _detect_browser_global(message: str) -> Optional[str]:
    """
    Return the browser global named in a Node ``ReferenceError`` message, or
    ``None`` if the failure is not a known browser-only global.

    Matches Node's phrasing ``"<name> is not defined"`` and only classifies it
    as browser-only when ``<name>`` is in ``JS_BROWSER_GLOBALS`` — an unrelated
    ``ReferenceError`` (a genuine typo) is left to surface normally.
    """
    if not message or JS_NOT_DEFINED_SUFFIX not in message:
        return None
    # Message looks like "document is not defined"; take the leading token.
    name = message.split(JS_NOT_DEFINED_SUFFIX, 1)[0].strip()
    return name if name in JS_BROWSER_GLOBALS else None

# Static Node wrapper — reads the invocation payload from an env var so file
# paths / function names can never be interpolated into executable JS source.
_JS_WRAPPER = """
// zOS runtime seam: a zFunc always runs server-side (Node), never in a browser.
// Well-behaved plugins can branch on this instead of crashing, e.g.
//   if (!globalThis.zOS.isBrowser) return computeOnly(...);
globalThis.zOS = Object.freeze({ runtime: 'node', isBrowser: false });
const { pathToFileURL } = require('url');
const payload = JSON.parse(process.env.ZFUNC_JS_PAYLOAD);
(async () => {
    // Load via dynamic import() so BOTH ESM (export fn) and CommonJS plugins
    // resolve — browser plugins are authored ESM (the page loads them with
    // import()), and require() would throw ERR_REQUIRE_ESM at load time, BEFORE
    // the function ever runs (so a browser-only DOM access could never surface as
    // the classifiable "document is not defined"). Mirror the browser resolver:
    // named export first, then default[fn].
    let mod;
    try {
        mod = await import(pathToFileURL(payload.module_path).href);
    } catch (e1) {
        // A `.js` with `export`/`import` but no package.json "type":"module" is
        // classified CJS by Node, so import(path) throws "Unexpected token export"
        // at parse time. The browser always treats these as ESM; do the same here
        // by importing the source as a data: URL (always ESM). Lets a self-
        // contained browser plugin actually run → DOM access becomes classifiable.
        try {
            const src = require('fs').readFileSync(payload.module_path, 'utf8');
            mod = await import('data:text/javascript,' + encodeURIComponent(src));
        } catch (e2) {
            console.error(JSON.stringify({ __error__: true, message: e1.message, stack: e1.stack }));
            process.exit(1);
        }
    }
    const func = (mod && typeof mod[payload.func_name] === 'function')
        ? mod[payload.func_name]
        : (mod && mod.default && typeof mod.default[payload.func_name] === 'function'
            ? mod.default[payload.func_name]
            : null);
    if (typeof func !== 'function') {
        console.error(JSON.stringify({ __error__: true, message: `Function '${payload.func_name}' not found in module` }));
        process.exit(1);
    }
    try {
        const result = await func(...payload.args);
        // A zFunc that returns nothing (undefined) is almost always GUI-only — it
        // painted to the DOM and fell off the end. JSON.stringify(undefined) is
        // itself undefined, which would print the bare word "undefined" and break
        // JSON parsing on the Python side. Emit a typed void marker instead so zOS
        // can no-op gracefully (render nothing) rather than crash.
        if (result === undefined) {
            console.log(JSON.stringify({ __zfunc_void__: true }));
        } else {
            console.log(JSON.stringify(result));
        }
    } catch (error) {
        console.error(JSON.stringify({ __error__: true, message: error.message, stack: error.stack }));
        process.exit(1);
    }
})();
"""

# Marker emitted by the Node wrapper when a JS zFunc returns nothing (undefined).
# Surfaces to zOS as a clean no-op (None) — see execute_js_function.
_JS_VOID_KEY = "__zfunc_void__"


# ============================================================================
# Helper Functions
# ============================================================================

def check_node_available(logger_instance: Any) -> bool:
    """
    Check if Node.js is available on the system.
    
    Parameters
    ----------
    logger_instance : Any
        Logger instance for debug messages.
        
    Returns
    -------
    bool
        True if Node.js is available, False otherwise.
    """
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger_instance.debug(DEBUG_MSG_NODE_VERSION, result.stdout.strip())
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ============================================================================
# Public API
# ============================================================================

def execute_js_function(
    file_path: str,
    func_name: str,
    args: List[Any],
    logger_instance: Any,
    zos: Optional[Any] = None
) -> Any:
    """
    Execute a JavaScript function from a file using Node.js.
    
    This function executes a JavaScript function by spawning a Node.js subprocess,
    passing arguments as JSON, and parsing the returned JSON result.
    
    The JavaScript file must export the function using CommonJS (module.exports)
    or ES6 (export) syntax.
    
    Parameters
    ----------
    file_path : str
        Absolute or relative path to the JavaScript file containing the function.
        The file must exist and be readable.
        
    func_name : str
        Name of the exported function to execute.
        The function must be exported at module level.
        
    args : List[Any]
        List of arguments to pass to the function.
        Arguments will be serialized to JSON.
        
    logger_instance : Any
        Logger instance for debug and error messages.
        
    Returns
    -------
    Any
        The result returned by the JavaScript function.
        The result is parsed from JSON.
        
    Raises
    ------
    FileNotFoundError
        If Node.js is not found or the JavaScript file doesn't exist.
        
    subprocess.CalledProcessError
        If the JavaScript execution fails (non-zero exit code).
        
    json.JSONDecodeError
        If the JavaScript function doesn't return valid JSON.
        
    ValueError
        If the JavaScript function is not found in the module.
        
    Examples
    --------
    Example 1: Call a simple function
        >>> result = execute_js_function(
        ...     "/path/to/math.js",
        ...     "add",
        ...     [5, 3],
        ...     logger
        ... )
        >>> print(result)  # Output: 8
        
    Example 2: Handle errors
        >>> try:
        ...     result = execute_js_function("/path/to/script.js", "process", [data], logger)
        ... except FileNotFoundError:
        ...     print("Node.js or file not found")
        ... except subprocess.CalledProcessError as e:
        ...     print(f"Execution failed: {e.stderr}")
        
    Notes
    -----
    - **Node.js Required**: Node.js must be installed and available in PATH.
    - **JSON Serialization**: Arguments must be JSON-serializable.
    - **Return Value**: JavaScript function must return JSON-serializable data.
    - **Performance**: Each call spawns a new Node.js process (no caching).
    - **Security**: Only execute trusted JavaScript files.
    """
    # Check if Node.js is available
    if not check_node_available(logger_instance):
        raise FileNotFoundError(ERROR_MSG_NODE_NOT_FOUND)

    # Check if JavaScript file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(ERROR_MSG_JS_FILE_NOT_FOUND.format(file_path=file_path))

    # Trust gate (single door): JS runs as arbitrary code via Node, so it must
    # pass the same zGuard seam as Python plugin loading. Permissive no-op in
    # open-core; raises PluginTrustError when a sealed policy denies (propagates,
    # Node is never spawned).
    from zOS.L1_Foundation.c_zLoader.loader_modules.loader_trust import (
        verify_plugin_trust,
    )
    verify_plugin_trust(file_path, zos, logger_instance)

    logger_instance.debug(DEBUG_MSG_JS_CALL, file_path, func_name, args)

    # Invocation data passed as a JSON payload via env — never interpolated into
    # the script source, so a crafted path/func name cannot inject JS.
    payload = json.dumps({
        "module_path": file_path,
        "func_name": func_name,
        "args": args,
    })
    node_env = {**os.environ, "ZFUNC_JS_PAYLOAD": payload}

    try:
        # Execute Node.js with the static wrapper script. --no-warnings keeps
        # stderr clean: importing an ESM browser plugin as a data: URL otherwise
        # prints a "To load an ES module…" notice that would pollute our structured
        # error payload (and historically broke the browser-only classification).
        result = subprocess.run(
            ["node", "--no-warnings", "-e", _JS_WRAPPER],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_JS_EXECUTION,
            env=node_env
        )

        # Check for execution errors
        if result.returncode != 0:
            # Pull the wrapper's structured error out of stderr (robust to any
            # extra Node diagnostics that share the stream — see _extract_error_json).
            error_data = _extract_error_json(result.stderr)
            if error_data:
                message = error_data.get("message", "")
                if "not found in module" in message:
                    raise ValueError(ERROR_MSG_JS_FUNCTION_NOT_FOUND.format(
                        func_name=func_name,
                        file_path=file_path
                    ))
                # Browser-only failure (document/window/…): classify it so the
                # facade can render one clean warning instead of a traceback.
                browser_global = _detect_browser_global(message)
                if browser_global:
                    raise BrowserOnlyFunctionError(func_name, browser_global, file_path)
                raise RuntimeError(message or "Unknown error")

            raise subprocess.CalledProcessError(
                result.returncode,
                ["node"],
                output=result.stdout,
                stderr=result.stderr
            )

        # Parse the result as JSON
        try:
            stdout = result.stdout.strip()
            # Defensive: no stdout at all → treat as a void/no-op return rather
            # than a JSON crash (mirrors the undefined-return GUI-only case).
            if not stdout:
                logger_instance.debug(
                    "JS function '%s' produced no output — treating as void (GUI-only) no-op",
                    func_name,
                )
                return None
            parsed_result = json.loads(stdout)
            # GUI-only / no-return: the function painted (or did nothing) and
            # returned undefined. There is no JSON payload to inject — return a
            # clean None so the facade renders nothing instead of "null".
            if isinstance(parsed_result, dict) and parsed_result.get(_JS_VOID_KEY):
                logger_instance.debug(
                    "JS function '%s' returned no value (void) — likely GUI-only; "
                    "no JSON to inject into zOS",
                    func_name,
                )
                return None
            logger_instance.debug(DEBUG_MSG_JS_RESULT, parsed_result)
            return parsed_result
        except json.JSONDecodeError as e:
            logger_instance.error(ERROR_MSG_JS_RESULT_PARSE.format(error=str(e)))
            logger_instance.error("Raw output: %s", result.stdout)
            raise

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"JavaScript execution timed out after {TIMEOUT_JS_EXECUTION} seconds"
        ) from exc
    except BrowserOnlyFunctionError:
        # Expected, handled gracefully by the facade — don't log a traceback here.
        raise
    except Exception as e:
        logger_instance.error(
            ERROR_MSG_JS_EXECUTION_FAILED.format(
                file_path=file_path,
                func_name=func_name,
                error=str(e)
            ),
            exc_info=True
        )
        raise
