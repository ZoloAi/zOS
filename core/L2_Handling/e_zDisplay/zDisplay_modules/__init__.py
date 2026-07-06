# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/__init__.py

"""
zDisplay Modules
================

Internal implementation of the zDisplay subsystem. All modules here are
private to zDisplay — external code uses zDisplay directly, never these.

Layers (top → bottom):
    api/        Convenience methods (display.error(), display.header(), ...)
                Thin mixins that build event dicts and call handle().

    display_events.py
                Orchestrator. Instantiates and cross-wires the 10 event
                packages so they can call each other.

    basic/      Core event logic. Foundation used by all other event layers.
                Includes output rendering helpers and semantic_colors.

    compounds/  Complex interactive widgets built on basic/.
                Selection menus, media, links, buttons.

    advanced/   Markdown rendering, progress bars, spinners, zTable.

    system/     System UI — zDeclare, zMenu, zDialog, zSession, zCrumbs.

    io/         Terminal I/O syscall wrappers (print/input/getpass).
                WebSocket emitter for Bifrost mode.
                Mode-switching lives here, nowhere else.

    utils/      Pure stateless utilities — no I/O, no display reference.

    display_constants.py
                All event name strings and shared literals in one place.

See README.md for full dependency rules and event flow diagram.
"""
