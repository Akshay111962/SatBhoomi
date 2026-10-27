.PHONY: help install lint format test migrate seed run-api run-ui

help:
	@echo "SatBhoomi Score + Raksha - Development Commands"
	@echo "  make install   Install dependencies in editable mode with dev tools"
	@echo "  make lint      Run ruff linting and formatting checks"
	@echo "  make format    Format code using ruff"
	@echo "  make test      Run test suite with coverage report"
	@echo "  make migrate   Apply latest Alembic database migrations"
	@echo "  make seed      Seed database with synthetic demo data"
	@echo "  make run-api   Start FastAPI backend on http://localhost:8000"
	@echo "  make run-ui    Start Streamlit dashboard on http://localhost:8501"

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check src tests scripts alembic
	python -m ruff format --check src tests scripts alembic

format:
	python -m ruff format src tests scripts alembic
	python -m ruff check --fix src tests scripts alembic

test:
	python -m pytest --cov=src/satbhoomi tests/

migrate:
	alembic upgrade head

seed:
	python scripts/seed_synthetic.py

run-api:
	python -m uvicorn satbhoomi.api.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	python -m streamlit run src/satbhoomi/ui/app.py
