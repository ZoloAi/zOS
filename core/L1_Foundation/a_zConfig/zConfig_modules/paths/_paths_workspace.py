"""Workspace and dotenv detection for zConfigPaths."""

from zOS import Path, load_dotenv, Optional, Tuple, Any, Dict


class zConfigPathsWorkspace:
    """Workspace directory and dotenv file detection logic."""

    # Mixin type declarations (defined by sibling mixins in zConfigPaths)
    zSpark: Optional[Dict[str, Any]]
    workspace_dir: Optional[Path]
    _dotenv_path: Optional[Path]
    _verbose: bool
    DOTENV_KEY_ALIASES: tuple
    DOTENV_FILENAME: str
    ZENV_EXTENSIONS: list

    def _log_info(self, message: str) -> None: ...  # pylint: disable=unused-argument
    def _log_warning(self, message: str) -> None: ...  # pylint: disable=unused-argument

    def _detect_workspace_dir(self) -> Optional[Path]:
        """Determine workspace directory using zSpark hint or current directory."""
        if self.zSpark:
            workspace = self.zSpark.get("zSpace")
            if workspace:
                try:
                    return Path(workspace).expanduser().resolve()
                except Exception:  # pragma: no cover - defensive fallback
                    self._log_warning(
                        f"Unable to resolve zSpace '{workspace}', defaulting to current directory"
                    )

        try:
            return Path.cwd()
        except Exception:  # pragma: no cover - defensive fallback
            return Path.home()

    def _resolve_explicit_dotenv_path(self) -> Optional[Path]:
        """Check zSpark configuration for explicitly provided dotenv path."""
        if not self.zSpark:
            return None

        for key in self.DOTENV_KEY_ALIASES:
            candidate = self.zSpark.get(key)
            if candidate:
                try:
                    return Path(candidate).expanduser().resolve()
                except Exception:  # pragma: no cover - defensive fallback
                    self._log_warning(f"Invalid dotenv path '{candidate}' from zSpark key '{key}'")
        return None

    def _detect_dotenv_file(self) -> Optional[Path]:
        """Determine dotenv file location from zSpark overrides or workspace.

        Detection priority:
        1. Explicit path from zSpark configuration (via DOTENV_KEY_ALIASES)
        2. .zEnv in workspace directory (primary convention)
        3. .env in workspace directory (backward compatibility)
        4. Returns .zEnv path even if neither exists (for potential creation)
        """
        explicit = self._resolve_explicit_dotenv_path()
        if explicit:
            return explicit

        if self.workspace_dir:
            zenv_path = self.workspace_dir / self.DOTENV_FILENAME
            if zenv_path.exists():
                return zenv_path

            env_path = self.workspace_dir / ".env"
            if env_path.exists():
                self._log_info("Using .env file (consider migrating to .zEnv)")
                return env_path

            return zenv_path

        return None

    def get_dotenv_path(self) -> Optional[Path]:
        """Return resolved dotenv path (.zEnv or .env fallback).

        Returns:
            Path to dotenv file (may not exist), or None if no workspace
        """
        return self._dotenv_path

    def _find_zenv_files(self, deployment: str) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Find zEnv config files with extension auto-detection.

        This is the decision layer - it discovers which files exist.
        File loading is delegated to config_zenv.py (the execution layer).

        Args:
            deployment: Deployment environment (development, production, testing)

        Returns:
            tuple: (base_file_path, env_file_path) or (None, None)
        """
        base_file = None
        env_file = None

        for ext in self.ZENV_EXTENSIONS:
            candidate = self.workspace_dir / f"zEnv.base{ext}"
            if candidate.exists():
                base_file = candidate
                break

        for ext in self.ZENV_EXTENSIONS:
            candidate = self.workspace_dir / f"zEnv.{deployment}{ext}"
            if candidate.exists():
                env_file = candidate
                break

        return base_file, env_file

    def load_dotenv(self, override: bool = True) -> Optional[Path]:
        """Load environment variables with STRICT zEnv priority over dotenv.

        THE zOS WAY (v2.0): Priority-based loading with declarative-first guarantee:
        1. Try zEnv.base.{zolo|yaml} + zEnv.{deployment}.{zolo|yaml} (declarative, THE zOS WAY)
        2. Fallback to .zEnv + .zEnv.{deployment} ONLY if NO config files exist

        IMPORTANT: If ANY zEnv config files exist (even if empty/malformed),
        dotenv fallback is SKIPPED. This ensures declarative files always take precedence.

        Args:
            override: Whether to override existing environment variables (default: True)

        Returns:
            Path to loaded file, or None if no file found/loaded

        Example (THE zOS WAY):
            # zEnv.base.zolo
            ZNAVBAR:
              zVaF:
              zAccount:
                zRBAC:
                  require_role: [zAdmin]

            # zEnv.production.zolo (overrides)
            DEPLOYMENT: Production
            HTTP_SSL_ENABLED(bool): true
            HTTP_SSL_CERT: /etc/ssl/cert.pem
        """
        from zOS import os

        # ─── PRIORITY 1: Try zEnv (ZOLO/YAML) - THE zOS WAY ────────────────────

        deployment = "development"
        if self.zSpark:
            for key in ("zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT"):
                if key in self.zSpark:
                    deployment = str(self.zSpark[key]).lower()
                    break

        if not deployment or deployment == "development":
            env_deployment = os.getenv('DEPLOYMENT') or os.getenv('ZOLO_DEPLOYMENT')
            if env_deployment:
                deployment = env_deployment.lower()

        base_file, env_file = self._find_zenv_files(deployment)
        config_files_exist = base_file is not None or env_file is not None

        if config_files_exist:
            try:
                from ..environment.config_zenv import zEnv

                workspace_dir = str(self.workspace_dir)
                zenv_loader = zEnv(workspace_dir, deployment, logger=None)
                loaded = zenv_loader.load_files(base_file, env_file)

                if loaded:
                    self._log_info(f"Loaded zEnv (THE zOS WAY) for {deployment} environment")
                    return env_file if env_file else base_file
                else:
                    self._log_warning("⚠️  zEnv files exist but failed to load, skipping dotenv fallback")
                    return None

            except Exception as e:
                self._log_warning(f"⚠️  zEnv loading error: {e}, but config files exist - skipping dotenv fallback")
                return None

        # ─── PRIORITY 2: Dotenv-only mode (no YAML configs in workspace) ──────────
        # Only reached if NO YAML files exist in workspace

        dotenv_path = self.get_dotenv_path()
        if not dotenv_path:
            self._log_info("No dotenv path resolved")
            return None

        if not dotenv_path.exists():
            self._log_warning(f"Dotenv file not found at: {dotenv_path}")
            return None

        loaded = load_dotenv(dotenv_path, override=override)
        if loaded:
            self._log_info(f"Loaded environment variables from: {dotenv_path}")
        else:
            self._log_warning(f"Dotenv file present but no variables loaded: {dotenv_path}")

        # Cascading .zEnv support (v1.5.10): Load deployment-specific overrides
        deployment_check = None
        if self.zSpark:
            for key in ["zEnv", "zState", "deployment", "Deployment", "DEPLOYMENT"]:
                if key in self.zSpark:
                    deployment_check = str(self.zSpark[key])
                    break

        if not deployment_check:
            deployment_check = os.getenv('DEPLOYMENT')

        if deployment_check:
            deployment_env_path = dotenv_path.parent / f".zEnv.{deployment_check.lower()}"
            if deployment_env_path.exists():
                deployment_loaded = load_dotenv(deployment_env_path, override=True)
                if deployment_loaded:
                    self._log_info(f"Loaded deployment-specific env: {deployment_env_path.name}")
                else:
                    self._log_warning(
                        f"Deployment env file present but no variables loaded: {deployment_env_path.name}"
                    )

        return dotenv_path
