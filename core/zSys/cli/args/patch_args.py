"""
Patch Command Arguments

Defines CLI arguments for the 'patch' command which detects and fixes
Python ABI mismatches between the running interpreter and bundled zguard binaries.
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "patch",
        help="Fix zOS environment (ABI mismatch, Playwright browsers, agent context)",
        description=(
            "Self-heals the zOS environment:\n"
            "  1. Detects Python ABI mismatches and reinstalls via uv if needed.\n"
            "  2. Installs Playwright Chromium binaries for zRaven browser tests.\n"
            "  3. Updates AI agent context (z agents)."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed environment info",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="After patching, self-replace every running zServer with the patched "
             "code (zero-downtime SIGUSR2 swap — no restart needed)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the 24h binary trust window: refetch zguard binaries from "
             "the repo unconditionally, ignoring the cached VERSION's recheck "
             "clock (use right after a zguard_bin/ push, when the CDN may still "
             "serve a stale VERSION that re-blesses the old build)",
    )
    return parser
