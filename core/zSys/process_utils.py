# zSys/process_utils.py
"""
process_utils — cross-platform process probes. Layer 0, stdlib-only.

pid_alive() exists because the POSIX idiom ``os.kill(pid, 0)`` is a LANDMINE on
Windows: there os.kill with any sig other than CTRL_C_EVENT/CTRL_BREAK_EVENT
calls TerminateProcess — "probing" pid liveness would KILL the process. Every
liveness check in the codebase must go through this function.
"""

import os

_STILL_ACTIVE = 259                             # GetExitCodeProcess: process running
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def pid_alive(pid) -> bool:
    """True if *pid* is a live process. Never signals/kills anything."""
    if not isinstance(pid, int) or pid <= 0:
        return False

    if os.name == "nt":
        import ctypes  # pylint: disable=import-outside-toplevel
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False  # no such process (or fully access-denied — treat as gone)
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)  # sig 0 = pure existence probe on POSIX
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False


__all__ = ["pid_alive"]
