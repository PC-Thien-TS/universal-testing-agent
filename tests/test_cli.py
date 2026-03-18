from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "web_booking.yaml"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UTA_TIMEOUT_WEB_MS"] = "1000"
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_validate_manifest_command() -> None:
    proc = _run_cli("validate-manifest", str(SAMPLE_MANIFEST))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_plan_command_creates_output_file() -> None:
    plan_file = PROJECT_ROOT / "results" / "plan_latest.json"
    if plan_file.exists():
        plan_file.unlink()
    proc = _run_cli("plan", str(SAMPLE_MANIFEST))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert plan_file.exists()


def test_run_and_report_commands_create_outputs() -> None:
    result_file = PROJECT_ROOT / "results" / "latest.json"
    report_file = PROJECT_ROOT / "results" / "report_latest.json"

    if result_file.exists():
        result_file.unlink()
    if report_file.exists():
        report_file.unlink()

    run_proc = _run_cli("run", str(SAMPLE_MANIFEST))
    assert run_proc.returncode == 0, run_proc.stdout + run_proc.stderr
    assert result_file.exists()

    report_proc = _run_cli("report", str(result_file))
    assert report_proc.returncode == 0, report_proc.stdout + report_proc.stderr
    assert report_file.exists()
