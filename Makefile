.PHONY: help install lint format test migrate seed run-api run-ui fetch-ndvi fetch-rainfall fetch-prices build-dataset build-features train score

help:
	@echo "SatBhoomi Score + Raksha - Development Commands"
	@echo "  make install         Install dependencies in editable mode with dev tools"
	@echo "  make lint            Run ruff linting and formatting checks"
	@echo "  make format          Format code using ruff"
	@echo "  make test            Run test suite with coverage report"
	@echo "  make migrate         Apply latest Alembic database migrations"
	@echo "  make seed            Seed database with synthetic demo data"
	@echo "  make fetch-ndvi      Fetch multi-season NDVI observations for sample plots"
	@echo "  make fetch-rainfall  Fetch multi-season daily rainfall for sample plots"
	@echo "  make fetch-prices    Fetch multi-season mandi commodity prices"
	@echo "  make build-dataset   Assemble multi-source seasonal training/evaluation dataset"
	@echo "  make build-features  Extract pre-cutoff features and compute proxy stress labels"
	@echo "  make train           Train baseline heuristics and ML models, evaluating held-out season"
	@echo "  make score           Score one plot-season (ANAND_WHEAT_01, 2024-25) and print JSON"
	@echo "  make run-api         Start FastAPI backend on http://localhost:8000"
	@echo "  make run-ui          Start Streamlit dashboard on http://localhost:8501"

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	python -m ruff format --check src tests
	python -m ruff check src tests

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

fetch-ndvi:
	python scripts/fetch_ndvi.py --provider fixture

fetch-rainfall:
	python scripts/fetch_rainfall.py --provider fixture

fetch-prices:
	python scripts/fetch_prices.py --provider manual_csv

build-dataset:
	python scripts/build_dataset.py

build-features:
	python scripts/build_features.py

train:
	python scripts/train_models.py

score:
	python scripts/score_plot.py --plot ANAND_WHEAT_01 --season 2024-25

