# zOS/zAgents — AI instruction build + install system
# Generates and provisions zolo agent instructions to LLM/IDE tooling

from .builder import build_all
from .agents_cli import run as inject

__all__ = ["build_all", "inject"]
