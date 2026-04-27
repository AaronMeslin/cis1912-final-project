# syntax=docker/dockerfile:1
# Sandboxed Agent Execution Platform — agent workspace image.
# TODO: Pin distro versions; drop capabilities; seccomp/AppArmor profiles.

# -----------------------------------------------------------------------------
# Stage 1: tooling baseline (optional separate stage for cache + smaller final layer churn)
# -----------------------------------------------------------------------------
FROM debian:bookworm-slim AS tooling

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Node.js + npm from Debian (stub; pin version or use official node image in a later stage)
# TODO: Pin Node major (e.g. copy from node:20-bookworm-slim) if distro packages lag.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Python + pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Headless Chromium + deps for Puppeteer/Playwright-style use
# TODO: Trim package list to minimum required for Chromium; consider official Playwright image instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

WORKDIR /workspace

# -----------------------------------------------------------------------------
# Stage 2: final runtime image
# -----------------------------------------------------------------------------
FROM tooling AS runtime

# TODO: NETWORK_ALLOWLIST — enforce via iptables/nftables or Docker network + proxy only.
# TODO: Read-only mounts: run container with --read-only + tmpfs for /tmp, /workspace writes via volume policy.
# TODO: seccomp, no-new-privileges, user namespace.

LABEL org.opencontainers.image.title="SAEP Sandbox"
LABEL org.opencontainers.image.description="Isolated workspace for AI coding agents"

COPY pyproject.toml /tmp/saep/pyproject.toml
COPY snapshot /tmp/saep/snapshot
COPY orchestrator /tmp/saep/orchestrator
COPY sandbox/healthcheck.sh /usr/local/bin/saep-healthcheck

RUN chmod +x /usr/local/bin/saep-healthcheck \
    && python3 -m pip install --break-system-packages /tmp/saep \
    && groupadd --system agent \
    && useradd --system --gid agent --home-dir /workspace --shell /bin/bash agent \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace

WORKDIR /workspace
USER agent

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/saep-healthcheck"]

# Default command: keep container alive for `docker exec` workflows; override in orchestration.
CMD ["bash", "-lc", "echo SAEP sandbox ready; sleep infinity"]
