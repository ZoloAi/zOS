"""zHost — the control-plane subsystem (L4 Orchestration).

zServer serves *one* app (the data plane). zHost decides *which* app, brings it
up, and hands the visitor off (the control plane). It is the peer-above that
orchestrates zServers: the front door, instance lifecycle, and — later — fleet
blue-green + deploy.

Entrypoint imports only. All behaviour lives in ``zHost_modules``.
"""

from .zHost import zHost

__all__ = ["zHost"]
