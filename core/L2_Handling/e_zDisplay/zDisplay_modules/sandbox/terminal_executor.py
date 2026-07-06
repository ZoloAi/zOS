# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/sandbox/terminal_executor.py

"""
Terminal Code Execution (zTerminal)
===================================

Runs code embedded in ``zTerminal`` events. This executes on the operator's
LOCAL machine in zCLI mode — it is NOT a secure sandbox and is not advertised as
one. Foreign / untrusted ``.zolo`` content must never be allowed to reach this
path on a machine the operator does not control.

Trust contract (fail-closed)
-----------------------------
- Bifrost mode: this executor returns immediately. Remote execution is handled
  by the sealed WebSocket ``execute_code`` path, gated by zGuard. Note Bifrost
  never honours ``trust`` — it clamps to ``sandbox``; ``trust`` is local-only.
- Local (zCLI) mode: ``readonly`` is the baked-in default — execution is OFF
  unless the operator explicitly opts in via zEnv ``ZTERMINAL_MODE``:
    * ``readonly`` — render the code, never execute (also: absent / empty /
      unknown all resolve here). The safe default.
    * ``sandbox``  — Python only, restricted builtins (best-effort, NOT a
      security boundary against hostile code).
    * ``trust``    — operator fully trusts the content (local desktop). Python
      runs; bash remains unimplemented in open-core (sealed path only).
  Keeping ``readonly`` as the default removes the silent-auto-run risk: a
  checked-out repo with foreign zTerminal content cannot execute unless the
  operator wrote ``sandbox`` / ``trust`` into their own zEnv.
- ``display_trust.verify_terminal_exec`` is the proprietary attestation seam on
  top of the config gate (zGuard); permissive in open-core.

Honest limitations
-------------------
The Python path uses a restricted-builtins ``exec`` and injects the live zOS
instance as ``z`` for ergonomics. That is convenient, not airtight — a
determined payload can reach framework internals. The real boundary is the
fail-closed config gate above: don't enable ``ZTERMINAL_MODE`` for content you
do not trust.

Supported languages: python, bash (disabled in open-core), zui.
"""

from zOS import Optional, Any, re, os
from zOS.zVocabulary import ZMODE_ZCLI, ZMODE_ZBIFROST

from .display_trust import verify_terminal_exec
from .sandbox_policy import build_safe_builtins

# zEnv policy vocabulary for the local execution gate (see zEnv.base.zolo).
# No legacy values. readonly is the baked-in default (also: unset / unknown);
# sandbox and trust REQUIRE an explicit ZTERMINAL_MODE opt-in in zEnv.
ZTERMINAL_MODE_KEY = "ZTERMINAL_MODE"
ZTERMINAL_POLICY_READONLY = "readonly"
ZTERMINAL_POLICY_SANDBOX = "sandbox"
ZTERMINAL_POLICY_TRUST = "trust"
# Bifrost short-circuit value (protocol SSOT in zVocabulary).
_MODE_BIFROST = ZMODE_ZBIFROST


class TerminalExecutor:
    """Local code executor for zTerminal events (zCLI mode).

    Fail-closed: runs only when the operator declares ``ZTERMINAL_MODE`` in zEnv.
    See module docstring for the full trust contract. Not a security sandbox.
    """
    
    def __init__(self, display_instance: Any) -> None:
        """Initialize terminal executor with display instance.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zos = display_instance.zos
        self.zEvents = display_instance.zEvents
        self.mode = display_instance.mode
    
    def execute(
        self,
        content: str,
        language: str = "python",
        title: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """Execute code in sandbox and return output.
        
        Args:
            content: Code to execute
            language: Language (python, bash, zui)
            title: Optional title for display
            **kwargs: Display-only zTerminal properties (e.g. zRun) that the
                executor accepts and ignores — they affect rendering, not run.
        
        Returns:
            Captured output or None
        """
        # Bifrost mode: Skip execution (sealed WS execute_code path, zGuard-gated)
        if self.mode == _MODE_BIFROST:
            return None

        # Fail-closed local gate: zTerminal runs only when the operator opted in
        # via zEnv. readonly / absent / empty / unknown => render-only, no exec.
        policy = self._terminal_policy()
        if policy not in (ZTERMINAL_POLICY_SANDBOX, ZTERMINAL_POLICY_TRUST):
            self.zEvents.warning(
                "zTerminal is read-only — set ZTERMINAL_MODE: sandbox "
                "(or trust) in zEnv to enable local execution",
                indent=0,
            )
            return None

        # Proprietary attestation/integrity seam (zGuard). Permissive in
        # open-core; a sealed policy denial propagates as TerminalTrustError or
        # returns False here.
        if not verify_terminal_exec(content, language, policy, self.zos,
                                    getattr(self.zos, "logger", None)):
            self.zEvents.error("zTerminal execution blocked by trust policy", indent=0)
            return None

        # Parse code fences (```python ... ```)
        code_content, detected_lang = self._parse_code_fence(content)
        if detected_lang:
            language = detected_lang
        
        # Display header
        if title:
            self.zEvents.header(f"[{title}]", color="CYAN", indent=0, style="single")
        
        # Display code being executed
        self.zEvents.code(content=code_content, language=language, indent=0)

        # zRun gate — zCLI twin of the Bifrost Run button. Mirrors zImage's
        # open_prompt: show the snippet, then ask before executing. The walker
        # continues either way. zRun=False opts out entirely (display-only,
        # exactly like open_prompt=False on a media event).
        run_opt = kwargs.get("zRun", True)
        if isinstance(run_opt, str):
            run_opt = run_opt.strip().lower() not in ("false", "no", "0", "off")
        if not run_opt:
            self.zEvents.info(
                "Run disabled (zRun: false) — snippet shown for copy only.",
                indent=0,
            )
            return None
        if not self._confirm_run():
            from ..utils.confirm_gate import is_flat
            if not is_flat(self.display):
                # zFlat already rendered the inert affordance — no decline line.
                self.zEvents.warning("Run cancelled.", indent=0)
            return None

        # Execute based on language
        if language.lower() == "python":
            return self._execute_python(code_content)
        elif language.lower() == "bash":
            return self._execute_bash()
        elif language.lower() == "zui":
            return self._execute_zui(code_content, title)
        else:
            self.zEvents.warning(f"Language '{language}' not yet supported", indent=0)
            return None
    
    def _confirm_run(self) -> bool:
        """zCLI confirm gate before executing a zTerminal snippet.

        Mirrors the zImage/zVideo ``open_prompt`` pattern: render the snippet,
        then ask ``Run this snippet? (y/n)``. Delegates to the SSOT confirm_gate
        so prompt wording, colouring, validation and zFlat all live in one place.
        """
        from ..utils.confirm_gate import confirm_gate
        return confirm_gate(self.display, "run", label="Run")

    def _terminal_policy(self) -> str:
        """Read the local execution policy from zEnv ``ZTERMINAL_MODE``.

        Returns the normalized policy string, or "" when unset / unreadable so
        the gate fails closed.

        zEnv is owned by the zConfig subsystem — reach down to it via
        ``config.environment.get_env_var`` (the SSOT accessor, which surfaces the
        live zEnv-backed value). zTerminal never reads ``os.environ`` itself.
        """
        try:
            cfg = getattr(self.zos, "config", None)
            env_cfg = getattr(cfg, "environment", None)
            value = None
            if env_cfg is not None and hasattr(env_cfg, "get_env_var"):
                value = env_cfg.get_env_var(ZTERMINAL_MODE_KEY)
        except Exception:
            return ""
        return str(value).strip().lower() if value else ""

    def _parse_code_fence(self, content: str) -> tuple[str, Optional[str]]:
        """Parse code fence and extract content and language.
        
        Args:
            content: Raw content (may include ```python ... ```)
        
        Returns:
            Tuple of (code_content, detected_language)
        """
        fence_match = re.match(r'^```(\w+)?\s*\n?(.*?)(`{3,})\s*$', content, re.DOTALL)
        if fence_match:
            detected_lang = (fence_match.group(1) or 'text').lower()
            inner_content = fence_match.group(2)
            closing_backticks = fence_match.group(3)
            
            # Handle nested fences (6+ backticks)
            if len(closing_backticks) > 3:
                remaining_backticks = '`' * (len(closing_backticks) - 3)
                inner_content = inner_content.rstrip() + remaining_backticks
            
            return inner_content.strip(), detected_lang
        return content.strip(), None
    
    def _execute_python(self, code_content: str) -> Optional[str]:
        """Execute Python code in restricted sandbox.
        
        Args:
            code_content: Python code to execute
        
        Returns:
            None (output displayed directly)
        """
        # Wrap Python's input() to use zDisplay.read_string()
        def sandbox_input(prompt=""):
            return self.display.read_string(prompt)

        # Restricted builtins + import allow-list come from the shared SSOT so the
        # local (zCLI) and sealed (Bifrost) sandboxes can never drift. The live
        # instance is exposed as ``z`` for ergonomics (not a security boundary —
        # see sandbox_policy / the ZTERMINAL_MODE gate above).
        SAFE_BUILTINS = build_safe_builtins(extra={"input": sandbox_input})
        exec_globals = {"__builtins__": SAFE_BUILTINS, "z": self.zos}

        try:
            exec(code_content, exec_globals, {})  # pylint: disable=exec-used
            return None
        except NameError as e:
            self.zEvents.error(f"Sandbox Error: {e} (blocked for security)", indent=0)
            return None
        except ImportError as e:
            self.zEvents.error(f"Sandbox Error: {e}", indent=0)
            return None
        except Exception as e:
            self.zEvents.error(f"Error: {type(e).__name__}: {e}", indent=0)
            return None
    
    def _execute_bash(self) -> Optional[str]:
        """Bash execution disabled for security.
        
        Returns:
            None (error message displayed)
        """
        self.zEvents.error("Bash execution is unimplemented in open-core (sealed path only)", indent=0)
        self.zEvents.info("Use 'python' or 'zui' instead", indent=0)
        return None
    
    def _execute_zui(self, code_content: str, title: Optional[str]) -> Optional[str]:
        """Execute zUI code through full zWalker pipeline.
        
        Args:
            code_content: zUI code to execute
            title: Optional title for swap file
        
        Returns:
            None (output displayed directly)
        """
        try:
            # Sanitize title for filename
            sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', title or 'zTerminal_Swap')
            sanitized_title = re.sub(r'_+', '_', sanitized_title).strip('_') or 'zTerminal_Swap'
            
            # Swap file in zSpace
            zspace = self.zos.session.get('zSpace', os.getcwd())
            swap_filename = f"zUI.{sanitized_title}.zolo"
            swap_path = os.path.join(zspace, swap_filename)
            
            # Write content to swap file
            with open(swap_path, 'w', encoding='utf-8') as swap_file:
                swap_file.write(code_content)
            
            try:
                from zOS import zOS as zOS_Class
                
                zSpark = {
                    "zEnv": "Production",
                    "title": f"zTerminal: {title or 'Swap'}",
                    "zLog": "PROD",
                    "zMode": ZMODE_ZCLI,
                    "zSpace": zspace,
                    "zVaFolder": "@",
                    "zVaFile": f"zUI.{sanitized_title}",
                    "zBlock": "zVaF",
                }
                
                # Run new zOS instance
                z_temp = zOS_Class(zSpark)
                z_temp.run()
            finally:
                # Clean up swap file
                if os.path.exists(swap_path):
                    os.unlink(swap_path)
            
            return None
        except Exception as e:
            self.zEvents.error(f"Zolo Error: {e}", indent=0)
            return None
