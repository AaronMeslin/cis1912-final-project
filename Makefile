# Sandboxed Agent Execution Platform — developer tasks
.PHONY: build test dev sandbox-up sandbox-down lint

IMAGE_NAME ?= saep-sandbox
IMAGE_TAG ?= local
SANDBOX_CONTAINER ?= saep-sandbox-dev
PYTHON ?= python3

build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f sandbox/Dockerfile sandbox

test:
	$(PYTHON) -m compileall -q snapshot
	$(PYTHON) -m pytest tests/snapshot

lint:
	@echo "TODO: add ruff/black when pyproject.toml exists"
	$(PYTHON) -m compileall -q snapshot

dev:
	cd control-plane && npx wrangler dev

sandbox-up:
	docker rm -f $(SANDBOX_CONTAINER) 2>/dev/null || true
	docker run -d --name $(SANDBOX_CONTAINER) -p 9223:9222 $(IMAGE_NAME):$(IMAGE_TAG) sleep infinity
	@echo "Sandbox container: $(SANDBOX_CONTAINER) (stub: attach shell with docker exec -it $(SANDBOX_CONTAINER) bash)"

sandbox-down:
	docker rm -f $(SANDBOX_CONTAINER) 2>/dev/null || true
	@echo "Stopped and removed $(SANDBOX_CONTAINER) if it was running."
