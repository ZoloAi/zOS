# zOS/core/L2_Handling/i_zFunc/zFunc.py

"""
External Python function loader and executor.

Refactored in v1.6.0:
    - Simplified to thin facade pattern
    - Delegates execution to PythonExecutor
    - Follows b_zComm facade pattern
    - Execution logic extracted to executors subpackage
"""



__version__ = "1.0.0"
def _mask_passwords_in_data(data, mask='********'):
    """
    Recursively mask password values in dicts/lists for secure logging.
    
    Args:
        data: Dict, list, or other data structure to mask
        mask: String to use for masking (default: '********')
        
    Returns:
        Masked copy of the data
    """
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            # Check if key contains 'password' (case-insensitive)
            if isinstance(key, str) and 'password' in key.lower():
                masked[key] = mask
            else:
                masked[key] = _mask_passwords_in_data(value, mask)
        return masked
    elif isinstance(data, list):
        return [_mask_passwords_in_data(item, mask) for item in data]
    elif isinstance(data, tuple):
        return tuple(_mask_passwords_in_data(item, mask) for item in data)
    else:
        return data


class zFunc:
    """
    Function loading and execution subsystem.
    
    Thin facade delegating to specialized managers:
    - PythonExecutor: Python function execution
    - plugin_resolver: Plugin function execution
    - plugin_loader: Plugin module loading
    
    Refactored in v1.6.0:
        - Extracted execution logic to PythonExecutor
        - Simplified facade to delegation pattern
        - Following b_zComm facade pattern
    """

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos):
        """Initialize zFunc with zOS framework instance."""
        self.zos = zos
        self.logger = zos.logger
        self.display = zos.display
        self.zparser = zos.zparser
        self.mycolor = "ZFUNC"

        # Initialize executor for Python functions
        from .zFunc_modules.executors import PythonExecutor
        self._python_executor = PythonExecutor(zos)

        self.display.zDeclare("zFunc Ready", color=self.mycolor, indent=0, style="full")

    @property
    def module_cache(self):
        """
        Facade property for backward compatibility.
        
        DEPRECATED: Use zos.loader.cache directly instead.
        
        Delegates to zLoader's PythonModuleCache (single source of truth).
        This property maintains backward compatibility for code that accesses
        zos.zfunc.module_cache while the actual implementation lives in zLoader.
        
        Returns
        -------
        PythonModuleCache
            The unified Python module cache from zLoader
            
        Raises
        ------
        DeprecationWarning
            This property is deprecated and will be removed in a future version.
        """
        import warnings
        warnings.warn(
            "zFunc.module_cache is deprecated. Use zos.loader.cache directly instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.zos.loader.cache.python_module_cache

    def handle(self, zHorizontal, zContext=None):
        """Execute external Python function with given spec and context."""
        # Locator-complete: a `&.` plugin spec resolves through the folder-aware
        # plugin SSOT (same as run()). Callers that reach handle() directly — the
        # command-string parser, wizard-step values, nav-menu builders — could
        # previously only use @./~. (parse_function_path strips @/~, never &).
        # Routing `&.` here makes the plugin locator work everywhere @. does.
        if isinstance(zHorizontal, str) and zHorizontal.startswith('&.'):
            return self._run_plugin(zHorizontal, context=zContext)
        # Typed signal for browser-only JS (DOM in a Node subprocess) — handled
        # gracefully below rather than surfaced as a traceback.
        from .zFunc_modules.func_js_executor import BrowserOnlyFunctionError
        # Mask passwords in display and logs for security
        masked_horizontal = _mask_passwords_in_data(zHorizontal)
        self.logger.debug("zFunc.handle() invoked:")
        self.logger.debug("zHorizontal: %s", masked_horizontal)

        if zContext:
            masked_context = _mask_passwords_in_data(zContext)
            for k, v in masked_context.items():
                self.logger.debug("  %s: %s", k, v)
        else:
            self.logger.debug("zContext: None")

        try:
            # Step 1: Parse function path using zParser (reuses symbol resolution)
            func_path, arg_str, function_name = self.zparser.parse_function_path(
                zHorizontal,
                zContext
            )
            self.logger.debug("Parsed => func_path: %s, arg_str: %s, function_name: %s",
                            func_path, arg_str, function_name)

            # Step 2: Parse arguments
            args = self._parse_args(arg_str, zContext)
            self.logger.debug("Prepared args: %s", _mask_passwords_in_data(args))

            # Merge model ONLY when a schema model is actually set (zData-style
            # calls). A zDialog/zBtn onSubmit carries model=None, and injecting
            # {"model": None} as the first positional arg corrupted plain plugin
            # calls (e.g. hello_name received the dict → "Hello [object Object]").
            # TODO(zFunc/SDK): scope this strictly to the zData path so model is
            #   never injected into arbitrary plugin args — plugins should read it
            #   from context / declare a `model` param via the SDK.
            if zContext and isinstance(zContext, dict) and zContext.get("model") is not None:
                model = zContext["model"]
                if args and isinstance(args[0], dict):
                    args[0]["model"] = model
                else:
                    args.insert(0, {"model": model})
                self.logger.debug("Args after model merge: %s", _mask_passwords_in_data(args))

            # Step 3: Resolve callable
            func = self._resolve_callable(func_path, function_name)
            self.logger.debug("Resolved: %s.%s", func.__module__, func.__name__)

            # Step 4: Execute function — capture stdout in Bifrost so print() reaches the console signal
            import io as _io, sys as _sys
            _bifrost = getattr(getattr(self, 'display', None), 'mode', '') == 'zBifrost'
            if _bifrost:
                _buf = _io.StringIO()
                _old_stdout = _sys.stdout
                _sys.stdout = _buf
            try:
                result = self._python_executor.execute(func, args, zContext)
            finally:
                if _bifrost:
                    _sys.stdout = _old_stdout
                    _stdout_output = _buf.getvalue()
                else:
                    _stdout_output = None
            self.logger.debug("Execution result: %s", _mask_passwords_in_data(result))

            # Step 5: Display result (zCLI only — Bifrost signal sent by the walker)
            self._display_result(result, stdout_output=_stdout_output)

            return result

        except BrowserOnlyFunctionError as e:
            return self._handle_browser_only(e)

        except Exception as e:
            self.logger.error("zFunc execution error: %s", e, exc_info=True)
            raise

    def _handle_browser_only(self, e):
        """Render-agnostic graceful path for a browser-only `.js` zFunc.

        A `.js` zFunc that touches the DOM (document/window/…) can't run in a
        Node subprocess — identically on zCLI and zBifrost. It returned NO usable
        data, so per the zCLI feedback policy it is the "nothing came back"
        bucket → ONE SOFT error signal (a calm line, not a traceback) that points
        the author at zScripts. Returns None so the walker keeps going. Shared by
        both locators (& and @.) so the feedback is identical no matter how the
        function was reached.
        """
        from .zFunc_modules.func_constants import (
            WARN_MSG_JS_BROWSER_ONLY,
            LOG_MSG_JS_BROWSER_ONLY,
        )
        self.logger.warning(
            LOG_MSG_JS_BROWSER_ONLY, e.file_path, e.func_name, e.global_name
        )
        try:
            self.display.error(
                WARN_MSG_JS_BROWSER_ONLY.format(
                    func_name=e.func_name, global_name=e.global_name
                )
            )
        except Exception:
            pass
        return None

    def run(self, func_spec, context=None):
        """SSOT dispatch entry for a zFunc/plugin invocation.

        Locator-agnostic. ``&name`` (auto-mounted plugin folders) and ``@.path``
        (explicit zPath) are two ways to LOCATE the same callable — once resolved,
        execution and the on-screen result MUST be identical. Language (Python /
        JS) is irrelevant here too: both land on the same path.

        Returns the RAW result unchanged (consumers rely on it: zData hooks,
        zOpen, zGuard). The on-screen render is a side-effect kept in lockstep
        across both locators.

        Phase 1 unifies the zCLI locator parity: ``&`` used to return WITHOUT any
        display, so a return-only plugin printed nothing while the ``@.`` form
        rendered its return — the locator silently changed the output. Now both
        render the same way.

        # TODO(zFunc/SDK): converge fully onto ZResult.coerce + one renderer so
        #   the envelope consumers (zDialog/zBtn success-error, Bifrost signals)
        #   are locator/language agnostic too. Phase 2 routes JS results through
        #   coerce; Phase 3 wires Bifrost + dialog/btn consumers to the envelope.
        """
        is_str = isinstance(func_spec, str)
        if is_str and func_spec.startswith('&.'):
            # &. → plugin-folder resolution. Shared with handle() via _run_plugin
            # so both entry points are indistinguishable for the plugin locator.
            return self._run_plugin(func_spec, context)
        if is_str and func_spec.startswith('&'):
            # Bare "&plugin.fn()" (no leading dot) is not canon — fail loudly
            # with guidance instead of silently mis-resolving as a @. zPath.
            raise ValueError(
                f"Invalid plugin invocation: {func_spec}\n"
                "The plugin sigil is '&.' — the leading dot is part of it "
                "(like @. / ~.). Use &.plugin[.subfolder].function(args)."
            )
        # @.path → existing facade path (zPath resolution; displays in zCLI,
        # stashes for the walker in Bifrost).
        return self.handle(func_spec, zContext=context)

    def _run_plugin(self, func_spec, context=None):
        """Resolve + execute a ``&.`` plugin locator and render like the @. path.

        Single SSOT for the plugin locator, shared by run() (zUI dispatch) and
        handle() (command-string parser, wizard-step values, nav-menu builders).
        Before this, handle() could only resolve @./~. — parse_function_path
        strips @/~ but never &, so a ``&.`` zFunc broke in those contexts while
        ``@.`` worked everywhere. Routing through here closes that SSOT split.
        Render its return the SAME way the @. path does so the two locators are
        indistinguishable on screen. Bifrost envelope wiring is Phase 3.
        """
        from .zFunc_modules.func_js_executor import BrowserOnlyFunctionError
        try:
            result = self.execute_plugin(func_spec, context)
        except BrowserOnlyFunctionError as e:
            # Same graceful warning the @. path gets — locator parity for JS too.
            return self._handle_browser_only(e)
        if getattr(getattr(self, 'display', None), 'mode', '') != 'zBifrost':
            self._display_result(result)
        return result

    def execute_plugin(self, value: str, context=None):
        """
        Execute plugin function from parsed syntax.
        
        Main entry point for plugin execution. Delegates to plugin_resolver
        which handles loading, caching, and execution.
        
        Args:
            value: Plugin invocation string (e.g., "&test_plugin.hello('Alice')")
            context: Optional context for wizard/hat access
            
        Returns:
            Plugin function result
            
        Examples:
            >>> result = zos.zfunc.execute_plugin("&test_plugin.hello('Alice')")
            "Hello, Alice!"
            
            >>> result = zos.zfunc.execute_plugin("&math.add(5, 3)")
            8
        """
        from .zFunc_modules.plugin_resolver import resolve_plugin_invocation
        return resolve_plugin_invocation(value, self.zos, context)

    def load_plugin(self, plugin_name: str):
        """
        Load plugin module by name.
        
        Searches standard plugin paths and loads module into cache.
        
        Args:
            plugin_name: Plugin filename (without .py), e.g., "test_plugin"
            
        Returns:
            Loaded module object
            
        Examples:
            >>> module = zos.zfunc.load_plugin("test_plugin")
            >>> module.some_function()
        """
        from .zFunc_modules.plugin_loader import load_plugin_module
        return load_plugin_module(plugin_name, self.zos)

    def zNow(self, format_type: str = "datetime", custom_format=None):
        """
        Get current date/time formatted per zConfig.
        
        Convenience wrapper for the zNow built-in function.
        
        Args:
            format_type: "date", "time", or "datetime" (default: "datetime")
            custom_format: Override config format (e.g., "yyyy-mm-dd")
            
        Returns:
            Formatted date/time string
            
        Examples:
            >>> zos.zfunc.zNow()  # "19122025 14:30:00"
            >>> zos.zfunc.zNow('date')  # "19122025"
            >>> zos.zfunc.zNow('time')  # "14:30:00"
            >>> zos.zfunc.zNow(custom_format='yyyy-mm-dd')  # "2025-12-19"
        """
        from .zFunc_modules.builtin_functions import zNow
        return zNow(format_type=format_type, custom_format=custom_format, zos=self.zos)

    def zUUID(self):
        """
        Generate a random UUID v4 string.

        Convenience wrapper for the zUUID built-in function.

        Returns:
            Canonical lowercase 8-4-4-4-12 hex string.

        Examples:
            >>> zos.zfunc.zUUID()  # "550e8400-e29b-41d4-a716-446655440000"
        """
        from .zFunc_modules.builtin_functions import zUUID
        return zUUID()

    def _parse_args(self, arg_str, zContext):
        """Parse arguments."""
        from .zFunc_modules.arg_processing import process_arguments, split_arguments
        return process_arguments(arg_str, zContext, split_arguments, self.logger, self.zparser)

    def _resolve_callable(self, func_path, function_name):
        """Resolve callable (gated: routes Python/JS loading through zLoader's trust seam)."""
        from .zFunc_modules.func_resolver import resolve_callable
        return resolve_callable(func_path, function_name, self.logger, self.zos)

    def _display_result(self, result, stdout_output=None):
        """Surface a zFunc result as ONE zSignal (zCLI) or stash it (Bifrost).

        zCLI feedback policy — result-based, no source scanning. Reuses the
        existing zSignal renderers (success/warning/error) so a plugin author
        always gets feedback, and the *signal* itself is the softness (a calm
        line, never a traceback). Three branches, identical for eager ``zFunc:``
        and button ``action:`` (one SSOT):

          • data, no error/gui      → SUCCESS  ("all green" — JSON came back)
          • data + error and/or gui → WARNING  (mixed — partial result)
          • no data (void/gui/error)→ ERROR, SOFT (browser/GUI-only or empty —
                                       nothing usable returned; skipped gracefully)
        """
        if getattr(getattr(self, 'display', None), 'mode', '') == 'zBifrost':
            if not hasattr(self.zos, '_zfunc_results'):
                self.zos._zfunc_results = []
            self.zos._zfunc_results.append({
                'result': result,
                'stdout': stdout_output.strip() if stdout_output else None,
            })
            return

        # SSOT envelope: normalise whatever the plugin returned (Python or JS,
        # bare value / dict / legacy {success,...}) into one ZResult so feedback
        # is uniform across languages and locators.
        from zos_plugin import ZResult
        zr = ZResult.coerce(result)
        gui = (zr.meta or {}).get('gui')
        effect = (gui.get('effect') if isinstance(gui, dict) else gui) if gui else None
        # "Has data" must reject empty payloads — coerce normalises a void/error
        # return to None or an empty {} / [] / "" (e.g. a legacy {success:false,
        # error:...} envelope yields data={}). Treat those as nothing-came-back so
        # they land in the soft-error branch, not the mixed/warning one. 0/False are
        # real values, so only empty containers/strings count as empty.
        has_data = zr.data is not None and zr.data not in ({}, [], "")
        has_msg = bool(zr.message)

        if zr.error:
            # Failed. With data alongside → mixed (warning); bare → soft error.
            if has_data:
                self.display.warning(str(zr.error))
                self._render_data(zr)
            else:
                self.display.error(str(zr.error))
        elif gui and (has_data or has_msg):
            # Browser effect AND something for the terminal → mixed (warning).
            self.display.warning(
                f"visual effect '{effect}' is browser-only — skipped in zCLI"
            )
            self._render_data(zr)
        elif has_data or has_msg:
            # All green → success. Message wins the headline; a string return is
            # its own headline; structured data renders below "done".
            if has_msg:
                line = zr.message
            elif isinstance(zr.data, str):
                line = zr.data
            else:
                line = "done"
            self.display.success(line)
            if has_data and not isinstance(zr.data, str):
                self._render_data(zr)
        else:
            # Nothing usable came back (void / gui-only) → soft error.
            if gui:
                msg = f"Visual effect '{effect}' is browser-only — nothing to run in zCLI."
            else:
                msg = "Function returned nothing — likely a browser/GUI effect; skipped gracefully."
            self.display.error(msg)

    def _render_data(self, zr) -> None:
        """Render the payload a data-bearing signal carries (string raw, structured as JSON)."""
        if zr.data is None:
            return
        if isinstance(zr.data, str):
            self.display.text(zr.data)
        else:
            self.display.json_data(zr.data, color=True, indent=0)
