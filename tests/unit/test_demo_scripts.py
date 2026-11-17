"""Unit tests for demo automation scripts (demo_setup.ps1 and demo_check.ps1).

Verifies:
1. Demo setup refuses an existing database without -Reset.
2. Demo setup refuses execution if target database matches the configured dev DB.
3. Demo check reports FAIL with exit code 1 when the API is down/unreachable.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

POWERSHELL_EXE = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"


@pytest.fixture
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.mark.skipif(
    sys.platform != "win32" and not shutil.which("powershell"),
    reason="PowerShell is required to test .ps1 automation scripts",
)
def test_demo_setup_refuses_existing_database_without_reset(
    project_root: Path, tmp_path: Path
) -> None:
    """Setup script must refuse to run if target database already exists unless -Reset is passed."""
    dummy_db = tmp_path / "dummy_demo.db"
    dummy_db.write_text("dummy database content", encoding="utf-8")
    assert dummy_db.is_file()

    script_path = project_root / "scripts" / "demo_setup.ps1"

    cmd = [
        POWERSHELL_EXE,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-DemoDbPath",
        str(dummy_db),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    assert proc.returncode != 0
    err_output = proc.stdout + proc.stderr
    assert "already exists" in err_output or "Refusing execution" in err_output


@pytest.mark.skipif(
    sys.platform != "win32" and not shutil.which("powershell"),
    reason="PowerShell is required to test .ps1 automation scripts",
)
def test_demo_setup_never_writes_to_configured_dev_db(project_root: Path) -> None:
    """Setup script must refuse execution if the target path equals the development database."""
    script_path = project_root / "scripts" / "demo_setup.ps1"

    # Attempt to target the development database
    cmd = [
        POWERSHELL_EXE,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-DemoDbPath",
        "data/satbhoomi.db",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    assert proc.returncode != 0
    err_output = proc.stdout + proc.stderr
    assert (
        "CRITICAL SAFETY REFUSAL" in err_output or "matches the development database" in err_output
    )


@pytest.mark.skipif(
    sys.platform != "win32" and not shutil.which("powershell"),
    reason="PowerShell is required to test .ps1 automation scripts",
)
def test_demo_check_reports_fail_when_api_is_down(project_root: Path) -> None:
    """Demo check must report FAIL and exit with code 1 when the API server is unreachable."""
    script_path = project_root / "scripts" / "demo_check.ps1"

    # Point to an unused local port where no server is listening
    cmd = [
        POWERSHELL_EXE,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-ApiUrl",
        "http://127.0.0.1:59999",
        "-Username",
        "test_officer",
        "-Password",
        "test_password",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    assert proc.returncode == 1
    output = proc.stdout + proc.stderr
    assert "[FAIL] 1. API Health Check" in output
    assert "API server is unreachable" in output
