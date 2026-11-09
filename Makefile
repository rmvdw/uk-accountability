.PHONY: setup check build preview refresh serve clean

# One command surface for every agent and environment. See README.md.

setup:  ## Install the pinned Python toolchain and dependencies (needs network for packages)
	uv sync --locked

check:  ## Lint, test and validate saved data. Never contacts statistical sources.
	uv run ruff check .
	uv run ruff format --check .
	PYTHONWARNDEFAULTENCODING=1 uv run pytest -q
	uv run python -m ukdash check

build:  ## Build the static site into site/ from saved data. Never contacts statistical sources.
	uv run python -m ukdash build

preview:  ## Build a review preview into site/ that includes draft indicators (never deploy to production).
	uv run python -m ukdash build --drafts

# `make refresh ID=<indicator>` fetches just that indicator, drafts included.
refresh:  ## Fetch live data, validate, build in staging; promote only if everything passes.
	uv run python -m ukdash refresh $(if $(ID),--indicator $(ID))

serve:  ## Serve whatever is in site/ at http://localhost:8000 (run make build or make preview first)
	uv run python -m http.server 8000 --directory site

clean:
	rm -rf site .pytest_cache .ruff_cache
