#!/usr/bin/env bash
# docker_baseline.sh — run the zOS baseline gate inside a Linux container.
#
# The cross-platform rung below "this Mac" and above "real cloud machines":
# a random-user Linux box, on either metal, without leaving this machine.
#
#   scripts/docker_baseline.sh                          # linux/arm64 (native on Apple Silicon)
#   scripts/docker_baseline.sh linux/arm64 --demos zHello,zTaskList
#
# Everything after the platform argument is passed through to zos_baseline.py.
# Reports land in ~/zos-baseline-runs/docker-<arch>/ on the host.
#
# linux/amd64 CAVEAT: emulated x86_64 containers boot zOS fine (zguard
# linux-x86_64 binaries import, WS-only suites pass) but Chromium CRASHES
# under QEMU user emulation — every browser suite fails at Open_App. Native
# x86_64 coverage lives in .github/workflows/baseline.yml (ubuntu runner)
# instead. Use linux/amd64 here only for boot/provisioning smoke checks.
#
# PREREQUISITE: zguard_bin/ on GitHub main must carry linux-aarch64 / linux-x86_64
# cp312 binaries (zGuard CI wheels → scripts/refresh_zguard_bin.py → push),
# otherwise zguard provisioning fails at boot and every suite is red.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == linux/* ]]; then
    PLATFORM="$1"; shift
else
    PLATFORM="linux/arm64"
fi
ARCH_SLUG="${PLATFORM#linux/}"
IMAGE="zos-baseline:${ARCH_SLUG}"
RUNS_DIR="${HOME}/zos-baseline-runs/docker-${ARCH_SLUG}"

echo "→ building ${IMAGE} for ${PLATFORM}"
# buildx, not the classic builder: classic `docker build --platform` silently
# builds for the host arch (an arm64 image tagged amd64), which docker run
# then refuses. buildx honors the platform via QEMU emulation.
docker buildx build --load --platform "$PLATFORM" -t "$IMAGE" \
    -f "$REPO_ROOT/scripts/docker_baseline/Dockerfile" \
    "$REPO_ROOT/scripts/docker_baseline"

mkdir -p "$RUNS_DIR"
echo "→ running baseline in ${PLATFORM} container (reports: ${RUNS_DIR})"
docker run --rm \
    --platform "$PLATFORM" \
    -v "$REPO_ROOT:/zos:ro" \
    -v "$RUNS_DIR:/root/zos-baseline-runs" \
    "$IMAGE" --keep "$@"
