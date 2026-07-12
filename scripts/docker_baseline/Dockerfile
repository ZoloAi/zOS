# zOS baseline container — a "random Linux user" machine in a box.
#
# Built per-arch (linux/arm64 native on Apple Silicon, linux/amd64 via
# emulation) by scripts/docker_baseline.sh. Bakes in the Playwright system
# libraries + Chromium so the runtime venv's `playwright install chromium`
# is a cheap revision check, not a cold download.
#
# zolo-os itself is NOT baked in: zos_baseline.py installs it from PyPI (or
# a mounted wheel) into a fresh venv at run time — that's the whole point.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Playwright system deps + Chromium, shared at the default registry path
# (~/.cache/ms-playwright) where zRaven's fallback lookup finds it.
RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# The zOS repo is bind-mounted read-only at /zos; git must trust it even
# though it is owned by the host user.
RUN git config --system --add safe.directory /zos

WORKDIR /zos
ENTRYPOINT ["python3", "scripts/zos_baseline.py"]
