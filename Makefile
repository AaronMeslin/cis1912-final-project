# Sandboxed Agent Execution Platform — developer tasks
.PHONY: build test dev orchestrator-dev orchestrator-test orchestrator-smoke sandbox-up sandbox-down sandbox-smoke lint

IMAGE_NAME ?= saep-sandbox
IMAGE_TAG ?= local
SANDBOX_CONTAINER ?= saep-sandbox-dev
ORCHESTRATOR_URL ?= http://127.0.0.1:9999
PYTHON ?= python3

build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f sandbox/Dockerfile .

test:
	$(PYTHON) -m compileall -q snapshot orchestrator
	$(PYTHON) -m pytest tests/snapshot tests/sandbox tests/orchestrator tests/control_plane

lint:
	@echo "TODO: add ruff/black when pyproject.toml exists"
	$(PYTHON) -m compileall -q snapshot orchestrator

dev:
	cd control-plane && npx wrangler dev

orchestrator-dev:
	saep-orchestrator

orchestrator-test:
	$(PYTHON) -m pytest tests/orchestrator tests/control_plane

orchestrator-smoke:
	@tmpfile=$$(mktemp); \
	trap 'rm -f "$$tmpfile"' EXIT; \
	curl -fsS -X POST "$(ORCHESTRATOR_URL)/sandboxes" > "$$tmpfile"; \
	sandbox_id=$$($(PYTHON) -c "import json, sys; print(json.load(open(sys.argv[1]))['sandboxId'])" "$$tmpfile"); \
	curl -fsS "$(ORCHESTRATOR_URL)/sandboxes/$$sandbox_id/health"; \
	curl -fsS -X DELETE "$(ORCHESTRATOR_URL)/sandboxes/$$sandbox_id"

sandbox-up:
	docker rm -f $(SANDBOX_CONTAINER) 2>/dev/null || true
	docker run -d --name $(SANDBOX_CONTAINER) -p 9223:9222 $(IMAGE_NAME):$(IMAGE_TAG) sleep infinity
	@echo "Sandbox container: $(SANDBOX_CONTAINER) (stub: attach shell with docker exec -it $(SANDBOX_CONTAINER) bash)"

sandbox-down:
	docker rm -f $(SANDBOX_CONTAINER) 2>/dev/null || true
	@echo "Stopped and removed $(SANDBOX_CONTAINER) if it was running."

sandbox-smoke:
	@tmpdir=$$(mktemp -d); \
	chmod 777 "$$tmpdir"; \
	trap 'rm -rf "$$tmpdir"' EXIT; \
	docker run --rm -v "$$tmpdir:/workspace" $(IMAGE_NAME):$(IMAGE_TAG) bash -lc "set -eu; safe-run run python3 -c \"from pathlib import Path; Path('hello.txt').write_text('hi', encoding='utf-8')\"; safe-run diff | tee /tmp/saep-diff.txt; grep -q 'created hello.txt' /tmp/saep-diff.txt; safe-run undo; test ! -e hello.txt"
