# zGuard — closed runtime core
# Provides: zguard.zengine, zguard.bifrost
#
# Version SSOT: pyproject.toml reads this attr (tool.setuptools.dynamic), the
# subpackages re-export it, and zOS's zguard_bin/<platform>/<py>/VERSION files
# are stamped from the wheel built at this version. Bump ONLY here.

__version__ = "1.0.7"
