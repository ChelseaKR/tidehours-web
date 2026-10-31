# The gate. CI's `verify` job runs `make verify` and nothing else, so a green
# `make verify` locally is the same claim as a green check.
#
# Needs: uv >= 0.9, gitleaks 8.x and osv-scanner 2.x on PATH.
# No recipe pipes one command into another: macOS make 3.81 ignores
# .SHELLFLAGS, so a pipe could hide a failure.

UV_RUN := uv run --frozen
SITE_TMP := $(shell mktemp -d 2>/dev/null || mktemp -d -t tidehours)

.PHONY: verify sync format lint typecheck test build-site audit secrets hygiene site-checks site

verify: sync format lint typecheck test build-site audit secrets hygiene
	@echo "verify: all gates passed"

sync:
	uv lock --check
	uv sync --frozen

format:
	$(UV_RUN) ruff format --check .

lint:
	$(UV_RUN) ruff check .

typecheck:
	$(UV_RUN) mypy --strict -p tidehours
	$(UV_RUN) mypy --strict scripts tests

# Includes the accuracy gate against NOAA (tests/test_golden.py) and the
# king-tide checks. Branch coverage floor: pyproject.toml.
test:
	$(UV_RUN) pytest --cov=src --cov-branch --cov-report=term

# The whole site, every station, with a pinned clock: proves a full build
# works and stays under the page-count floor.
build-site:
	$(UV_RUN) tidehours --out $(SITE_TMP)/site --now 2026-11-01T11:20:00Z
	$(UV_RUN) python scripts/check_site.py $(SITE_TMP)/site
	rm -rf $(SITE_TMP)/site

audit:
	uv export --frozen --no-emit-project --format requirements-txt --quiet --output-file $(SITE_TMP)/requirements.txt
	$(UV_RUN) pip-audit --strict --require-hashes --disable-pip -r $(SITE_TMP)/requirements.txt
	osv-scanner scan --lockfile uv.lock

secrets:
	gitleaks dir . --no-banner --redact --exit-code 1
	gitleaks git . --no-banner --redact --exit-code 1

hygiene:
	$(UV_RUN) python scripts/check_hygiene.py --self-test
	$(UV_RUN) python scripts/check_hygiene.py

# Accessibility (axe-core, pa11y-ci) over a sample of pages. Needs Node 22+
# and Chrome: (cd tools/site-checks && npm ci && npx puppeteer browsers install chrome)
site-checks:
	tools/site-checks/run.sh

# A local build with today's real numbers, for a look in the browser.
site:
	$(UV_RUN) tidehours --out site --base-url http://127.0.0.1:8000/
