$ErrorActionPreference = "Stop"

.venv\Scripts\python.exe -m ruff format --check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.venv\Scripts\python.exe -m ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

