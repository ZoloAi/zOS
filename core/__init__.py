# zOS/core/__init__.py
"""
zOS Package — Main Entry Point for the Zolo Framework
════════════════════════════════════════════════════

PACKAGE OVERVIEW
───────────────────────────────────────────────────────────────────────────────
zOS is the core Python framework for Zolo Media. It orchestrates 16 declarative
subsystems across four architectural layers, enabling developers to build modern
apps faster and more efficiently in the LLM era. It provides a mode-agnostic
output stack: zCLI (Terminal UI), zShell (REPL), and zBifrost (GUI via WebSocket).

ARCHITECTURE SUMMARY
─────────────────────────────────────────────────────────────────────────────────

zOS follows a 4-layer bottom-up architecture (L1_Foundation → L4_Orchestration):

    Layer 3: Orchestration (1 subsystem)
        • zWalker → UI/menu navigation orchestrator

    Layer 2: Core Abstraction (3 subsystems)
        • zWizard → Multi-step workflows (loop engine)
        • zData   → Database integration & declarative migrations
        • zShell  → Interactive REPL & command router

    Layer 1: Core Subsystems (9 subsystems)
        • zDisplay     → UI rendering & multi-mode output
        • zAuth        → Three-tier authentication & RBAC
        • zDispatch    → Command routing & dispatch
        • zNavigation  → Menu creation & breadcrumbs
        • zParser      → YAML parsing & configuration loading
        • zLoader      → File I/O, caching, & plugin management (6-tier)
        • zFunc        → Function execution & Python integration
        • zDialog      → Interactive forms & auto-validation
        • zOpen        → File & URL opening

    Layer 0: Foundation (2 subsystems + HTTP server)
        • zConfig → Session, logger, traceback, machine/env config
        • zComm   → Communication infrastructure (HTTP, WebSocket, zBifrost)

Note: zUtils subsystem removed in v1.7.0 - plugin management consolidated in zLoader

EXPORT STRATEGY
─────────────────────────────────────────────────────────────────────────────────

This package exports standard library modules and third-party dependencies to
provide a single import point for zCLI and its ecosystem. This simplifies imports
for plugins and applications:

    from zOS import zOS, json, yaml, Path, Optional
    # Instead of:
    # from zOS import zOS
    # import json
    # import yaml
    # etc...

PACKAGE CONSTANTS
─────────────────────────────────────────────────────────────────────────────────
See `zOS/core/meta.py` for package metadata and architecture counts.

See Also
--------
zOS.zOS : Main orchestrator class
get_current_zos : Thread-safe context access
"""

# pylint: disable=wrong-import-position,wrong-import-order

# Central imports for the entire zCLI system
# Standard library imports
import argparse
import ast
import asyncio
import base64
from contextlib import contextmanager
import functools
import getpass
import hashlib
import mimetypes
import importlib
import importlib.util
from importlib.metadata import distribution, PackageNotFoundError
import contextvars
import inspect
import json
import logging
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import traceback
import typing
import uuid
import webbrowser
from collections import OrderedDict
# NOTE: Do NOT import 'time' from datetime - it would overwrite the time module
# imported above (line 94). If datetime.time type is needed, use datetime.time directly.
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Awaitable, BinaryIO, Callable, Dict, Iterable, Iterator, List, NoReturn, Optional, Protocol, Set, Tuple, Union, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

# Third-party imports
import platformdirs  # pylint: disable=import-error  # type: ignore[import-not-found]
import requests  # pylint: disable=import-error  # type: ignore[import-not-found]
import yaml  # pylint: disable=import-error  # type: ignore[import-not-found]
import websockets  # pylint: disable=import-error  # type: ignore[import-not-found]
from websockets import serve as ws_serve  # pylint: disable=import-error  # type: ignore[import-not-found]
from websockets.legacy.server import WebSocketServerProtocol  # pylint: disable=import-error  # type: ignore[import-not-found]
from websockets import exceptions as ws_exceptions  # pylint: disable=import-error  # type: ignore[import-not-found]

# Optional third-party helper (fallback implementation if python-dotenv missing)
if importlib.util.find_spec("dotenv") is not None:
    from dotenv import load_dotenv  # pylint: disable=import-error  # type: ignore[import-not-found]
else:  # pragma: no cover - exercised when python-dotenv is unavailable
    def load_dotenv(dotenv_path=None, override=True):
        """Minimal fallback dotenv loader when python-dotenv is unavailable."""
        path = Path(dotenv_path) if dotenv_path else Path.cwd() / ".env"
        if not path.exists():
            return False

        loaded_any = False
        with path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                key, sep, value = line.partition("=")
                if not sep:
                    continue

                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if override or key not in os.environ:
                    os.environ[key] = value
                loaded_any = True

        return loaded_any

# ═══════════════════════════════════════════════════════════════════════════════
# PACKAGE CONSTANTS (SSOT: zOS/core/meta.py)
# ═══════════════════════════════════════════════════════════════════════════════

from .meta import (
    PACKAGE_AUTHOR,
    PACKAGE_LICENSE,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    SUBSYSTEM_COUNT,
    LAYER_COUNT,
    MODERNIZATION_COMPLETE,
    MODERNIZATION_DATE,
    MODERNIZATION_VERSION,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ROOT VOCABULARY (SSOT: zOS/core/zVocabulary.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Dependency-free leaf re-exported here so L2+/plugins can do
# `from zOS import SESSION_KEY_ZVAFILE`. L1 modules that load during boot should
# import the submodule directly (`from zOS.zVocabulary import ...`).
from . import zVocabulary
from .zVocabulary import *  # noqa: F401,F403  (canonical cross-subsystem vocab)

# ═══════════════════════════════════════════════════════════════════════════════
# ROOT PATH LOGIC (SSOT: zOS/core/zPath.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Dependency-free leaf (os + zVocabulary only) re-exported here so callers can do
# `from zOS import zPath` then `zPath.resolve_folder(...)`. L1 modules that load
# during boot should import the submodule directly (`from zOS.zPath import ...`).
from . import zPath

EXPORT_COUNT: int = 0  # Calculated below after __all__ definition

# Import utilities from zSys (Layer 0 - System Foundation)
from zSys.formatting import Colors  # pylint: disable=import-error

# Import JSON utilities (framework primitives for safe serialization)
from .L4_Orchestration.r_zServer.zServer_modules.utils.json_utils import safe_json_dumps

# Import the zCLI Core and Walker
from .engine import zOS

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# Export the main interfaces with type hint (List already imported above)
__all__: List[str] = [
    # Core class
    "zOS",

    # System modules
    "argparse",
    "ast",
    "asyncio",
    "base64",
    "contextmanager",
    "contextvars",
    "date",
    "datetime",
    "distribution",
    "functools",
    "getpass",
    "hashlib",
    "importlib",
    "inspect",
    "json",
    "logging",
    "mimetypes",
    "os",
    "Path",
    "platform",
    "platformdirs",
    "re",
    "requests",
    "secrets",
    "shutil",
    "signal",
    "socket",
    "sqlite3",
    "subprocess",
    "sys",
    "threading",
    "time",
    "timedelta",
    "traceback",
    "typing",
    "urlparse",
    "parse_qs",
    "uuid",
    "webbrowser",
    "websockets",
    "ws_exceptions",
    "ws_serve",
    "WebSocketServerProtocol",
    "yaml",
    "OrderedDict",
    "PackageNotFoundError",

    # Typing helpers
    "Any",
    "Awaitable",
    "BinaryIO",
    "Callable",
    "Dict",
    "Iterable",
    "Iterator",
    "List",
    "NoReturn",
    "Optional",
    "Protocol",
    "Set",
    "Tuple",
    "TYPE_CHECKING",
    "Union",

    # Third-party helpers
    "load_dotenv",

    # Utils
    "Colors",
    "safe_json_dumps",  # Framework primitive for NaN-safe JSON serialization
    "zPath",  # Root SSOT for zPath resolution logic (zPath.py)

    # Package Constants
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "PACKAGE_AUTHOR",
    "PACKAGE_LICENSE",
    "SUBSYSTEM_COUNT",
    "LAYER_COUNT",
    "EXPORT_COUNT",
    "MODERNIZATION_COMPLETE",
    "MODERNIZATION_VERSION",
    "MODERNIZATION_DATE",
] + list(zVocabulary.__all__)  # Root SSOT vocabulary (zVocabulary.py)

# Update EXPORT_COUNT after __all__ is defined
EXPORT_COUNT = len(__all__)
