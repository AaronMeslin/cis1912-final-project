from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_SOURCE = REPO_ROOT / "control-plane" / "src" / "index.ts"
WRANGLER_CONFIG = REPO_ROOT / "control-plane" / "wrangler.toml"


def test_worker_uses_orchestrator_proxy_instead_of_in_memory_registry() -> None:
    """The Worker should proxy to the local orchestrator instead of storing sandbox state."""
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert "new Map" not in source
    assert "sandboxRegistry" not in source
    assert "SANDBOX_ORCHESTRATOR_URL" in source
    assert "fetch(orchestratorUrl(request, env), init)" in source


def test_worker_enforces_public_auth_and_internal_orchestrator_token() -> None:
    """Public callers use Bearer auth; the Worker uses an internal token upstream."""
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert "API_KEY" in source
    assert "ORCHESTRATOR_TOKEN" in source
    assert "authorization" in source
    assert "Bearer ${env.API_KEY}" in source
    assert "x-saep-internal-token" in source
    assert "unauthorized" in source


def test_worker_routes_include_lifecycle_health_and_exec() -> None:
    """The Worker should expose all sandbox control routes."""
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert 'method: "POST", pattern: /^\\/sandbox\\/create$/' in source
    assert 'method: "GET", pattern: /^\\/sandbox\\/[^/]+\\/health$/' in source
    assert 'method: "POST", pattern: /^\\/sandbox\\/[^/]+\\/exec$/' in source
    assert 'method: "DELETE", pattern: /^\\/sandbox\\/[^/]+$/' in source


def test_worker_preserves_upstream_streaming_response_body() -> None:
    """SSE passthrough requires returning the upstream response body directly."""
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert "new Response(upstream.body" in source
    assert "headers: upstream.headers" in source
    assert "orchestrator_unavailable" in source


def test_wrangler_config_has_local_demo_auth_values() -> None:
    """Wrangler local dev should include both public and internal demo tokens."""
    config = WRANGLER_CONFIG.read_text(encoding="utf-8")

    assert 'SANDBOX_ORCHESTRATOR_URL = "http://127.0.0.1:9999"' in config
    assert 'API_KEY = "dev-api-key"' in config
    assert 'ORCHESTRATOR_TOKEN = "dev-internal-token"' in config
