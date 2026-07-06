# zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_policy.py
"""
zShell Bifrost seal-policy (SSOT).

Bifrost sessions are *always sandboxed* (see zBifrost trust model): a remote
web client must never be able to drive destructive or environment-mutating
shell commands on the host. This module is the single source of truth for which
``(command_type, action)`` pairs are sealed when the session runs in Bifrost
mode, and the router consults it before dispatching any command.

Scope (V3):
    - data delete / drop / migrate  → destructive / schema-altering
    - config set / reset            → mutates persisted host configuration

Read-only counterparts (data read/head/describe/status, config check/show/get)
remain available to the client. Unlike the V1 subprocess gate, this seal has no
operator opt-in: Bifrost is sandboxed unconditionally.
"""

from zOS import Any, Dict, Optional

from zOS.zVocabulary import ZMODE_ZBIFROST
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZMODE

from .executor_constants import CMD_TYPE_DATA, CMD_TYPE_CONFIG, KEY_TYPE, KEY_ACTION, KEY_ERROR
from .commands.shell_cmd_data import ACTION_DELETE, ACTION_DROP, ACTION_MIGRATE
from .commands.shell_cmd_config import ACTION_SET, ACTION_RESET

# command_type -> sealed actions (blocked when session mode is Bifrost)
SEALED_IN_BIFROST: Dict[str, frozenset] = {
    CMD_TYPE_DATA: frozenset({ACTION_DELETE, ACTION_DROP, ACTION_MIGRATE}),
    CMD_TYPE_CONFIG: frozenset({ACTION_SET, ACTION_RESET}),
}

ERROR_SEALED_IN_BIFROST: str = (
    "'{command} {action}' is sealed in a Bifrost (remote) session and can only "
    "be run from a local zCLI session."
)


REDACTION_PLACEHOLDER: str = "***"

# command -> subcommand -> index of the first token to redact (0-based over the
# whitespace-split command line). Secrets at/after this index are masked.
_SENSITIVE_ARGV: Dict[str, Dict[str, int]] = {
    "auth": {
        # auth login <user> <password...>  -> mask token 3+ (the password)
        "login": 3,
        # auth apikey verify <token>       -> mask token 3+ (the bearer token)
        "apikey": 3,
    },
}


def redact_sensitive_command(command: str) -> Optional[str]:
    """Return a history-safe copy of *command* if it carries inline secrets.

    Credentials must never be persisted to the readline history file. This is
    the SSOT for which command lines contain secrets on argv (e.g.
    ``auth login <user> <password>``). Returns ``None`` when nothing is sensitive
    so callers can leave history untouched.
    """
    tokens = command.split()
    if len(tokens) < 2:
        return None

    sub_map = _SENSITIVE_ARGV.get(tokens[0])
    if not sub_map:
        return None

    redact_from = sub_map.get(tokens[1])
    if redact_from is None or len(tokens) <= redact_from:
        return None

    # `auth apikey` only redacts the `verify <token>` form, not `issue/revoke`.
    if tokens[0] == "auth" and tokens[1] == "apikey" and tokens[2] != "verify":
        return None

    return " ".join(tokens[:redact_from] + [REDACTION_PLACEHOLDER])


def _is_bifrost(zos: Any) -> bool:
    """True only when the session is positively identified as Bifrost mode."""
    try:
        return zos.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST
    except Exception:  # pylint: disable=broad-except
        return False


def sealed_actions_for(zos: Any, command_type: str) -> frozenset:
    """Return the actions of *command_type* sealed for the current session.

    Empty unless the session is Bifrost — used by the help/UX layer (V5) so the
    shell never advertises a capability the seal-policy (V3) would block.
    """
    if not _is_bifrost(zos):
        return frozenset()
    return SEALED_IN_BIFROST.get(command_type, frozenset())


def enforce_bifrost_seal(zos: Any, parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Block sealed destructive/mutating commands in Bifrost sessions.

    Returns an error dict (router convention) when the command is sealed for the
    current session, otherwise ``None`` so dispatch may proceed.
    """
    if not _is_bifrost(zos):
        return None

    command_type = parsed.get(KEY_TYPE)
    sealed_actions = SEALED_IN_BIFROST.get(command_type)
    if not sealed_actions:
        return None

    action = parsed.get(KEY_ACTION)
    if action not in sealed_actions:
        return None

    msg = ERROR_SEALED_IN_BIFROST.format(command=command_type, action=action)
    try:
        zos.logger.warning(
            "Bifrost seal blocked command: type=%s action=%s", command_type, action
        )
        zos.display.error(msg)
    except Exception:  # pylint: disable=broad-except
        pass
    return {KEY_ERROR: msg}
