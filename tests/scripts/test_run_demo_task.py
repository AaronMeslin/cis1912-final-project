from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_demo_task.py"
spec = importlib.util.spec_from_file_location("run_demo_task", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
run_demo_task = importlib.util.module_from_spec(spec)
sys.modules["run_demo_task"] = run_demo_task
spec.loader.exec_module(run_demo_task)


class FakeResponse:
    def __init__(self, status_code: int, body: dict[str, Any] | None = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = text if text is not None else ""

    def json(self) -> dict[str, Any]:
        return self._body


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def delete(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("DELETE", url, kwargs))
        return self.responses.pop(0)


def sse(event: str, payload: dict[str, Any]) -> str:
    import json

    return f"event: {event}\ndata: {json.dumps(payload, sort_keys=True)}\n\n"


def test_run_demo_task_creates_execs_diffs_and_deletes_sandbox() -> None:
    diff_text = "modified demo-frontend/index.html (content changed)\nmodified demo-frontend/styles.css (content changed)\n"
    client = FakeClient(
        [
            FakeResponse(200, {"sandbox_id": "sandbox-1", "container_id": "container-1"}),
            FakeResponse(200, text=sse("exit", {"code": 0})),
            FakeResponse(200, text=sse("output", {"stream": "stdout", "line": diff_text}) + sse("exit", {"code": 1})),
            FakeResponse(200, {"sandbox_id": "sandbox-1", "status": "destroyed"}),
        ]
    )

    result = run_demo_task.run_demo_task(client, "http://worker.test", "key", 30)

    assert result.sandbox_id == "sandbox-1"
    assert result.diff_output == diff_text
    assert [call[0] for call in client.calls] == ["POST", "POST", "POST", "DELETE"]
    assert client.calls[0][1] == "http://worker.test/sandbox/create"
    assert client.calls[1][1] == "http://worker.test/sandbox/sandbox-1/exec"
    assert client.calls[1][2]["json"]["command"] == run_demo_task.DEMO_UPDATE_COMMAND
    assert client.calls[2][2]["json"]["command"] == ["safe-run", "diff"]
    assert client.calls[3][1] == "http://worker.test/sandbox/sandbox-1"


def test_run_demo_task_deletes_sandbox_when_demo_command_fails() -> None:
    client = FakeClient(
        [
            FakeResponse(200, {"sandbox_id": "sandbox-1", "container_id": "container-1"}),
            FakeResponse(200, text=sse("exit", {"code": 1})),
            FakeResponse(200, {"sandbox_id": "sandbox-1", "status": "destroyed"}),
        ]
    )

    with pytest.raises(run_demo_task.DemoTaskError, match="demo update command exited unexpectedly"):
        run_demo_task.run_demo_task(client, "http://worker.test", "key", 30)

    assert [call[0] for call in client.calls] == ["POST", "POST", "DELETE"]


def test_output_from_sse_extracts_only_output_events() -> None:
    body = sse("output", {"stream": "stdout", "line": "one\n"}) + sse("exit", {"code": 1})

    assert run_demo_task.output_from_sse(body) == "one\n"
