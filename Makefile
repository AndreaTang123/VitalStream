PY_SERVICES := libs/common services/ingestion services/feature_extraction services/config_service services/insight_service services/api

.PHONY: bootstrap test lint fmt up down frontend-install frontend-dev download-data

bootstrap:
	@for svc in $(PY_SERVICES); do \
		echo "==> $$svc"; \
		python3 -m venv $$svc/.venv; \
		$$svc/.venv/bin/pip install -q --upgrade pip; \
		$$svc/.venv/bin/pip install -q -e libs/common; \
		$$svc/.venv/bin/pip install -q -e $$svc'[dev]'; \
	done

test:
	@for svc in $(PY_SERVICES); do \
		echo "==> $$svc"; \
		$$svc/.venv/bin/pytest $$svc/tests -q || exit 1; \
	done

lint:
	@for svc in $(PY_SERVICES); do \
		$$svc/.venv/bin/ruff check $$svc/src || exit 1; \
	done

fmt:
	@for svc in $(PY_SERVICES); do \
		$$svc/.venv/bin/ruff format $$svc/src; \
	done

up:
	docker compose up -d

down:
	docker compose down

download-data:
	./data/scripts/download_datasets.sh

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev
