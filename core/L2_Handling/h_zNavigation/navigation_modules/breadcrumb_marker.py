# zOS/core/L2_Handling/h_zNavigation/navigation_modules/breadcrumb_marker.py

"""
Arrival-marker SSOT for the breadcrumb trail.

An *arrival marker* is the first entry seeded into a freshly-entered scope's
trail (by ``Breadcrumbs.seed_scope(arrival=True)`` / the Bifrost seeder). It is
the firewall ``handle_zBack`` reads to decide that the landed page is ONE unit:
a single zBack press leaves the whole page instead of unwinding its display
keys one at a time.

Why this lives alone
--------------------
The marker is ENGINE state — it is **not** a navigational key and **not** a
``zDelta`` link. Historically it borrowed the ``$`` glyph, which collides with
``$`` used everywhere else for zDelta links / zData vars / raven test vars. That
ambiguity is a latent bug: any code that treats a trail entry as a ``$``-delta
would mis-read an arrival sentinel. We retire the collision by giving arrival
its own glyph — ``α`` (alpha = arrival), fitting the Greek nav convention.

This module has **no imports from the navigation package**, so both the
``Breadcrumbs`` projector and the ``ZBackHandler`` (which ``Breadcrumbs``
imports — a circular path if the constant lived there) can share the ONE
definition. zGuard surfaces reach the same helpers at runtime via
``zos.navigation.breadcrumbs.{make_arrival,is_arrival,strip_arrival}``.
"""

from typing import Any

# The arrival glyph. NOT '$' (that is zDelta) — 'α' is reserved for the engine's
# scope-entry sentinel. Change it HERE and every writer/reader/projector follows.
ARRIVAL_MARK = "\u03b1"  # α


def make_arrival(block: str) -> str:
    """Build the arrival sentinel for a scope's block name (SSOT writer)."""
    return f"{ARRIVAL_MARK}{block}"


def is_arrival(key: Any) -> bool:
    """True iff ``key`` is an arrival sentinel (SSOT reader)."""
    return isinstance(key, str) and key.startswith(ARRIVAL_MARK)


def strip_arrival(key: str) -> str:
    """Return the clean block name behind an arrival sentinel (display SSOT)."""
    return key[len(ARRIVAL_MARK):] if is_arrival(key) else key
