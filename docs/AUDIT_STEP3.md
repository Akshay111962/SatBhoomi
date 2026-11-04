# Audit Report: Blueprint Task T-02 (Satellite NDVI Connector)

- **Date of Audit**: 2026-11-04
- **Auditor**: Antigravity Assistant (Read-Only Audit)
- **Target Task**: Task T-02 (Satellite NDVI fetch for sample plots, 5 seasons; Blueprint FR-003)
- **Overall Verdict**: **NOT DONE**

---

## 1. Executive Summary

A comprehensive read-only audit was conducted on repository health, satellite connector code, input/output datasets, live Earth Engine provider configuration, and test coverage for Blueprint Task **T-02**.

While repository hygiene, git tracking, schema models, and baseline project structure (T-01, T-10 partial) are healthy with 17 passing unit and integration tests, **Task T-02 itself has not been implemented**. The codebase contains only a 7-line placeholder stub at `src/satbhoomi/connectors/satellite.py`. No provider implementations (GEE, Planetary Computer, or fixture), aggregation logic, fetch scripts, or satellite datasets currently exist.

---

## 2. Audit Results Table

| Section | Audit Item | Expected per Blueprint / Task | Observed / Evidence | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **A. Repo** | Working Tree & Branch | Clean tracking of `main` | `On branch main`, ahead of origin by 1 commit (`b252497`). Untracked pre-existing blueprint PDF. | **PASS** |
| **A. Repo** | Commit History | Tracked progression | 4 commits: `b252497` (rules & progress), `5e3c540` (CI fix), `da12551` (DB layer), `c5e9eae` (T-01 foundation). | **PASS** |
| **A. Repo** | `make lint` execution | Formatter & linter pass | `make` not recognized on Windows host (`CommandNotFoundException`). Direct execution via `.venv\Scripts\ruff.exe` passed (`All checks passed! 44 files already formatted`). | **PARTIAL** (`make` missing; direct tools PASS) |
| **A. Repo** | `make test` execution | Automated tests pass | `make` not recognized on Windows host. Direct execution via `.venv\Scripts\pytest.exe` ran 17 tests: **17 passed** in 2.30s. | **PARTIAL** (`make` missing; direct tests PASS) |
| **A. Repo** | `.gitignore` rules | Covers `.env`, `data/raw/`, sqlite | Lines 26, 32-35, 38-43 explicitly ignore `.env`, `*.db`, `*.sqlite*`, and `data/raw/*`. | **PASS** |
| **A. Repo** | Secret scanning | No committed credentials | `git grep` detected zero real keys or tokens; only `.env.example` placeholders, synthetic hashes, and schema names. | **PASS** |
| **B. Code** | Satellite directory structure | `src/satbhoomi/connectors/satellite/` (`base`, `gee_provider`, `fixture_provider`, `aggregate`) | Directory does not exist. Only 7-line stub `src/satbhoomi/connectors/satellite.py` exists. | **NOT FOUND** |
| **B. Code** | Sentinel-2 Collection | Harmonized Surface Reflectance (`S2_SR_HARMONIZED`) | No satellite collection logic implemented in codebase. | **NOT FOUND** |
| **B. Code** | Cloud/Shadow Masking | Scene Classification Band (SCL) filtering | No SCL masking logic implemented. | **NOT FOUND** |
| **B. Code** | NDVI Formula | `NDVI = (B8 - B4) / (B8 + B4)` | Formula not implemented. | **NOT FOUND** |
| **B. Code** | Buffer Mean Extraction | Geometry buffer spatial reducer | Buffer mean extraction not implemented. | **NOT FOUND** |
| **B. Code** | Aggregator (`aggregate.py`) | Schema: `plot_code`, `season`, `ndvi_mean`, `ndvi_peak`, `ndvi_std`, `ndvi_early`, `valid_obs_count`, `data_gap`, `source`, `fetched_at` | File `aggregate.py` does not exist. | **NOT FOUND** |
| **B. Code** | Data Gap & Range Validation | Validates NDVI range `[-1, 1]`, season windows, never invents missing values | Validation logic does not exist. | **NOT FOUND** |
| **B. Code** | CLI Script `fetch_ndvi.py` | Flags `--provider`, `--dry-run`, caching, retry logic | File `scripts/fetch_ndvi.py` does not exist. | **NOT FOUND** |
| **B. Code** | Data Sources Documentation | `docs/DATA_SOURCES.md` | File does not exist. | **NOT FOUND** |
| **B. Code** | Makefile target `fetch-ndvi` | Target to run NDVI fetch CLI | `Makefile` contains only `help`, `install`, `lint`, `format`, `test`, `migrate`, `seed`, `run-api`, `run-ui`. | **NOT FOUND** |
| **B. Code** | T-02 Tests | Unit & integration tests for providers, masking, formulas, aggregation | Zero T-02 test files found under `tests/`. (Only DB model schema check mentions `ndvi_mean`). | **NOT FOUND** |
| **C. Inputs** | `data/synthetic/sample_plots.csv` | Sample plots coordinate CSV | File does not exist. (Only `.gitkeep` in `data/synthetic/`). | **NOT FOUND** |
| **C. Outputs** | `data/processed/ndvi_plot_season.csv` | Processed seasonal NDVI metrics | File does not exist. (Only `.gitkeep` in `data/processed/`). | **NOT FOUND** |
| **D. Live** | `GEE_PROJECT` configuration | Environment variable configured | Boolean check: `[bool]$env:GEE_PROJECT` returned `False`. Variable is unset. | **FAIL** (Unset) |
| **D. Live** | Live Provider Verification | Verified against live satellite data | No provider code exists and no live run executed. | **not verified against live data** |

---

## 3. Real Command Outputs

### 3.1 Git Status
```text
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	deleted:    doc/SatBhoomi_Blueprint_Idea_to_Plan.pdf

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	SatBhoomi_Blueprint_Idea_to_Plan.pdf

no changes added to commit (use "git add" and/or "git commit -a")
```

### 3.2 Git Commit Log (`git --no-pager log --oneline -15`)
```text
b252497 docs: add engineering rules, decisions and progress tracker
5e3c540 fix: add scripts/__init__.py and project root to pytest pythonpath for CI compatibility
da12551 feat: implement database layer with models, migrations, and synthetic seed
c5e9eae feat: initial project foundation (T-01)
```

### 3.3 Make Execution
- `make lint`:
  ```text
  make : The term 'make' is not recognized as the name of a cmdlet, function, script file, or operable program.
  ```
- Direct execution via Python virtualenv (`.venv\Scripts\ruff.exe`):
  ```text
  All checks passed!
  44 files already formatted
  ```

- `make test`:
  ```text
  make : The term 'make' is not recognized as the name of a cmdlet, function, script file, or operable program.
  ```
- Direct execution via Python virtualenv (`.venv\Scripts\pytest.exe`):
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.13.5, pytest-8.4.2, pluggy-1.7.0 -- D:\SatBhoomi\.venv\Scripts\python.exe
  rootdir: D:\SatBhoomi
  configfile: pyproject.toml
  testpaths: tests
  plugins: anyio-4.15.1, platformdirs-4.13.5, cov-5.0.0
  collected 17 items

  tests/integration/test_health.py::test_health_check_endpoint PASSED      [  5%]
  tests/integration/test_health.py::test_only_health_endpoint_registered PASSED [ 11%]
  tests/integration/test_migrations.py::test_alembic_upgrade_and_downgrade_cycle PASSED [ 17%]
  tests/unit/test_config.py::test_default_settings_loading PASSED          [ 23%]
  tests/unit/test_config.py::test_custom_environment_override PASSED       [ 29%]
  tests/unit/test_config.py::test_invalid_environment_validation PASSED    [ 35%]
  tests/unit/test_db.py::test_declarative_base_instantiation PASSED        [ 41%]
  tests/unit/test_db.py::test_sqlite_engine_creation_and_pragmas PASSED    [ 47%]
  tests/unit/test_postgresql_engine_configuration PASSED       [ 52%]
  tests/unit/test_db.py::test_get_db_session_generator PASSED              [ 58%]
  tests/unit/test_db.py::test_session_local_instantiation PASSED           [ 64%]
  tests/unit/test_models.py::test_area_acre_zero_or_negative_rejected PASSED [ 70%]
  tests/unit/test_models.py::test_duplicate_plot_season_rejected PASSED    [ 76%]
  tests/unit/test_models.py::test_assessment_without_model_version_rejected PASSED [ 82%]
  tests/unit/test_models.py::test_invalid_role_band_severity_status_rejected PASSED [ 88%]
  tests/unit/test_models.py::test_farmer_cascade_deletion PASSED           [ 94%]
  tests/unit/test_models.py::test_seed_synthetic_idempotency PASSED        [100%]
  ======================== 17 passed, 1 warning in 2.30s ========================
  ```

---

## 4. Numbered Gap List for Task T-02

1. **Connector Architecture Missing**: `src/satbhoomi/connectors/satellite.py` is an unpopulated 7-line stub. The required package `src/satbhoomi/connectors/satellite/` with base interface (`base.py`), Google Earth Engine provider (`gee_provider.py`), deterministic mock/fixture provider (`fixture_provider.py`), and seasonal feature aggregator (`aggregate.py`) has not been created.
2. **Satellite Processing Logic Missing**:
   - Sentinel-2 Level-2A Harmonized Surface Reflectance collection access.
   - SCL band cloud and shadow masking filters (cloud high/medium probability, cirrus, and shadow pixel exclusion).
   - Normalized Difference Vegetation Index formula `(B8 - B4) / (B8 + B4)`.
   - Spatial buffer reduction (e.g. 10m–30m circular buffer around coordinate point or polygon geometry mean).
3. **Seasonal Aggregation & Output Schema Missing**:
   - No calculation of seasonal aggregates: `ndvi_mean`, `ndvi_peak`, `ndvi_std`, `ndvi_early`, `valid_obs_count`, `data_gap`, `source`, `fetched_at`.
   - No validation logic to prevent value invention or clamp values outside `[-1.0, 1.0]`.
   - No season window definitions (e.g. Rabi season dates: November through March).
4. **Execution & CLI Pipeline Missing**:
   - `scripts/fetch_ndvi.py` does not exist (needs `--provider`, `--dry-run`, caching to `data/raw/`, and retry handling).
   - Makefile lacks `fetch-ndvi` target.
5. **Sample Datasets Missing**:
   - `data/synthetic/sample_plots.csv` does not exist (needed as input coordinates for the 5-season fetch).
   - `data/processed/ndvi_plot_season.csv` does not exist (the target output artifact for T-02).
6. **Documentation & Credentials Missing**:
   - `docs/DATA_SOURCES.md` does not exist.
   - `GEE_PROJECT` is unset in the environment and absent from `.env.example` and `Settings`.
7. **Test Suite Missing**:
   - Zero unit or integration tests exist for the satellite connector, providers, masking, formula, or aggregator.

---

## 5. Smallest Set of Actionable Fixes (for Implementation Phase)

When task T-02 is scheduled for implementation, the following minimal, focused set of changes should be built:

1. **Create Connector Module (`src/satbhoomi/connectors/satellite/`)**:
   - `base.py`: Abstract base class defining `fetch_plot_ndvi(geometry, start_date, end_date) -> list[Observation]`.
   - `fixture_provider.py`: Deterministic offline fixture provider enabling reproducible testing without GEE network access or credentials.
   - `gee_provider.py`: Earth Engine provider targeting `COPERNICUS/S2_SR_HARMONIZED`, masking clouds with `SCL`, computing `(B8 - B4) / (B8 + B4)`, and extracting buffer mean.
   - `aggregate.py`: Pure function computing seasonal metrics (`ndvi_mean`, `ndvi_peak`, `ndvi_std`, `ndvi_early`, `valid_obs_count`, `data_gap`), enforcing boundaries `[-1.0, 1.0]`, and applying date windows.
2. **Create Input Dataset (`data/synthetic/sample_plots.csv`)**:
   - Define a sample set of plots (e.g. 10–20 plots in target wheat district) with synthetic IDs and valid coordinate centroids.
3. **Create CLI Script (`scripts/fetch_ndvi.py`) & Makefile Target**:
   - CLI with `--provider=fixture|gee`, `--dry-run`, local caching in `data/raw/satellite/`, and writing output to `data/processed/ndvi_plot_season.csv`.
   - Add `fetch-ndvi` target to `Makefile`.
4. **Add Configuration & Documentation**:
   - Add `gee_project: str | None = None` to `src/satbhoomi/config/settings.py` and `.env.example`.
   - Create `docs/DATA_SOURCES.md` documenting satellite collection IDs, band indices, SCL mask values, and licensing.
5. **Write Comprehensive Tests (`tests/unit/test_satellite.py` & `tests/integration/test_satellite_pipeline.py`)**:
   - Test NDVI math formula with mock band inputs.
   - Test SCL cloud masking logic.
   - Test seasonal aggregation metrics, missing value handling, and `data_gap=True` flagging.
   - Test fixture provider end-to-end generating `data/processed/ndvi_plot_season.csv`.
