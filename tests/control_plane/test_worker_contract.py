from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_worker_proxies_lifecycle_routes_to_orchestrator() -> None:
    source = (REPO_ROOT / "control-plane" / "src" / "index.ts").read_text(encoding="utf-8")

    assert "sandboxRegistry" not in source
    assert "orchestratorRequest(env, \"/sandboxes\"" in source
    assert "orchestratorRequest(env, `/sandboxes/${id}/health`" in source
    assert "orchestratorRequest(env, `/sandboxes/${id}`" in source
    assert "upstream_not_configured" in source
