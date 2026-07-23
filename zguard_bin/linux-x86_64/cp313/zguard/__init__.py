# zGuard — closed runtime core
# Provides: zguard.zengine, zguard.bifrost
#
# Version SSOT: pyproject.toml reads this attr (tool.setuptools.dynamic), the
# subpackages re-export it, and zOS's zguard_bin/<platform>/<py>/VERSION files
# are stamped from the wheel built at this version. Bump ONLY here.

__version__ = "1.0.11"

# Grammar capabilities this build understands. zOS core checks this set at
# boot (zguard_provision.zguard_capability_gap) and warns LOUDLY when the
# loaded zguard is older than the grammar the app files use — the failure
# then names itself at rail-time instead of surfacing as a click-time
# "Unknown action type" toast (the 2026-07 zVar drift). Builds that predate
# this attribute report an empty set via getattr(), i.e. "old wheel".
#
# Add a token here IN THE SAME COMMIT that teaches the runtime the feature.
CAPABILITIES = frozenset({
    "zVar",       # declarative session-var writes in onSubmit
    "zLive",      # non-gating live dialogs (debounced auto-submit)
    "onSuccess",  # global onSuccess key on zDialog (zDelta refresh etc.)
})
