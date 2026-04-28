# Sandboxed Agent Execution Platform — developer tasks
.PHONY: build test dev orchestrator-test orchestrator-up e2e-smoke sandbox-up sandbox-down sandbox-smoke lint

IMAGE_NAME ?= saep-sandbox
IMAGE_TAG ?= local
SANDBOX_CONTAINER ?= saep-sandbox-dev
PYTHON ?= python3

build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f sandbox/Dockerfile .

test:
	$(PYTHON) -m compileall -q snapshot control-plane/orchestrator
	$(PYTHON) -m pytest tests/snapshot tests/sandbox tests/control_plane

lint:
	@echo "TODO: add ruff/black when pyproject.toml exists"
	$(PYTHON) -m compileall -q snapshot control-plane/orchestrator

dev:
	cd control-plane && npx wrangler dev

orchestrator-test:
	$(PYTHON) -m pytest tests/control_plane

orchestrator-up:
	cd control-plane && \
	SAEP_INTERNAL_TOKEN=dev-internal-token \
	uvicorn orchestrator.main:app --host 127.0.0.1 --port 9999 --reload

e2e-smoke:
	$(PYTHON) -m pytest -s tests/e2e -m e2e

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
