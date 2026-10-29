PYTHON ?= python3

.PHONY: help install lint format test check clean

help:
	@echo "install       Install the package with dev dependencies (editable)"
	@echo "lint          Ruff lint + format check"
	@echo "format        Apply Ruff fixes and formatting"
	@echo "test          Run the pytest suite (synthetic data only)"
	@echo "check         lint + test (what CI runs)"

install:
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	pytest -q -m "not live"

check: lint test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
