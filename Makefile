# The Last Safe Home — top-level targets (SPEC §13).
# Python runs inside the conda env `lsh`. Without conda, override PY, e.g.
#   make test PY=.venv/bin/python        (see docs/DECISIONS.md)

SHELL   := /bin/bash
ENV     ?= lsh
PY      ?= conda run --no-capture-output -n $(ENV) python
SITE    ?= manpura
STEP    ?= all
NPM     ?= npm

.PHONY: help setup demo inventory fetch pipeline api web test e2e lint up down build-web build-api pack static clean-site

help:
	@echo "targets: setup demo inventory fetch pipeline api web test e2e lint up down build-web build-api pack static clean-site"
	@echo "vars:    SITE=$(SITE) STEP=$(STEP) PY='$(PY)'"

setup:
	@echo ">> creating/updating conda env '$(ENV)' from environment.yml and installing web deps"
	conda env update -n $(ENV) -f environment.yml --prune
	cd web && $(NPM) install

demo:
	@echo ">> generating synthetic demo site -> data/processed/demo"
	$(PY) -m pipeline.cli all --site demo

inventory:
	@echo ">> searching NISAR for $(SITE) (no download) -> data/raw/$(SITE)/nisar/inventory.csv"
	$(PY) -m pipeline.cli fetch-nisar --site $(SITE) --dry-run

fetch:
	@echo ">> downloading NISAR + Landsat + context for $(SITE)"
	$(PY) -m pipeline.cli fetch-nisar --site $(SITE)
	$(PY) -m pipeline.cli landsat --site $(SITE)
	$(PY) -m pipeline.cli context --site $(SITE)

pipeline:
	@echo ">> running pipeline step '$(STEP)' for $(SITE)"
	$(PY) -m pipeline.cli $(STEP) --site $(SITE)

api:
	@echo ">> starting API on http://localhost:8000 (reload)"
	$(PY) -m uvicorn api.app.main:app --reload --port 8000

web:
	@echo ">> starting web dev server on http://localhost:5173"
	cd web && $(NPM) run dev

test:
	@echo ">> pipeline + API tests (pytest), web unit tests (vitest)"
	$(PY) -m pytest
	cd web && $(NPM) test

e2e:
	@echo ">> Playwright end-to-end tests against the demo site"
	cd web && npx playwright test

lint:
	@echo ">> ruff (python) + eslint (web)"
	$(PY) -m ruff check pipeline api
	cd web && $(NPM) run lint

up:
	@echo ">> docker compose: api + web with ./data/processed mounted read-only -> http://localhost:8080"
	DOCKER_BUILDKIT=1 docker compose up --build -d

down:
	@echo ">> stopping docker compose services"
	docker compose down

build-web:
	@echo ">> building web/dist (VITE_API_URL=$${API_URL:-http://localhost:8000})"
	cd web && VITE_API_URL=$${API_URL:-http://localhost:8000} $(NPM) run build

SITES ?= manpura,koyra,demo

pack:
	@echo ">> packing the served data of $(SITES) -> data/deploy (fails over 1.5 GB)"
	$(PY) -m pipeline.lsh.pack --sites $(SITES) --tar data/deploy/lsh-data.tar.gz

static:
	@echo ">> static edition (no API): exports $(SITES) -> data/static, builds web/dist-static"
	$(PY) -m api.static_export --sites $(SITES) --out data/static
	cd web && VITE_STATIC_URL=$${STATIC_URL:-/static} $(NPM) run build -- --outDir dist-static --emptyOutDir
	cp -r data/static web/dist-static/static
	@echo ">> serve web/dist-static from any static host (SPA fallback to index.html)"

build-api: pack
	@echo ">> building API docker image with the packed data"
	DOCKER_BUILDKIT=1 docker build -f api/Dockerfile -t last-safe-home-api .

clean-site:
	@test -n "$(SITE)" || (echo "SITE= is required" && exit 1)
	@echo ">> removing data/processed/$(SITE)"
	rm -rf data/processed/$(SITE)
