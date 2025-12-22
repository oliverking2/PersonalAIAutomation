.PHONY: help install lint format types test coverage check clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make install   Install dependencies"
	@echo "  make lint      Run Ruff linting with fixes"
	@echo "  make format    Run Ruff formatter"
	@echo "  make types     Run mypy type checking"
	@echo "  make test      Run unit tests"
	@echo "  make coverage  Run tests with coverage"
	@echo "  make check     Run lint, format, types, and coverage"
	@echo "  make clean     Remove caches and build artefacts"

install:
	poetry install

lint:
	poetry run ruff check --fix

format:
	poetry run ruff format

types:
	poetry run mypy .

test:
	poetry run python -m unittest discover testing/

coverage:
	poetry run coverage run -m unittest discover testing/
	poetry run coverage report --fail-under=80

check: lint format types coverage

clean:
	rm -rf .mypy_cache .ruff_cache .coverage htmlcov dist build
