#!/usr/bin/env bash
set -euo pipefail

for tool in git node python3 chromium safe-run; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "missing required tool: $tool" >&2
        exit 1
    }
done

test -w /workspace || {
    echo "/workspace is not writable" >&2
    exit 1
}
