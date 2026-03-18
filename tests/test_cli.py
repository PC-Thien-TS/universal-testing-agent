from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "web_booking.yaml"
API_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "api_verify_store.yaml"
MODEL_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "model_basalt.yaml"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UTA_TIMEOUT_WEB_MS"] = "500"
    env["UTA_TIMEOUT_API_S"] = "1"
    env["UTA_TIMEOUT_MODEL_S"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _assert_success(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_manifest_for_web_api_model() -> None:
    _assert_success(_run_cli("validate-manifest", str(WEB_MANIFEST)))
    _assert_success(_run_cli("validate-manifest", str(API_MANIFEST)))
    _assert_success(_run_cli("validate-manifest", str(MODEL_MANIFEST)))


def test_plan_for_web_api_model() -> None:
    _assert_success(_run_cli("plan", str(WEB_MANIFEST), "--output", "results/plan_web.json"))
    _assert_success(_run_cli("plan", str(API_MANIFEST), "--output", "results/plan_api.json"))
    _assert_success(_run_cli("plan", str(MODEL_MANIFEST), "--output", "results/plan_model.json"))
    assert (PROJECT_ROOT / "results" / "plan_web.json").exists()
    assert (PROJECT_ROOT / "results" / "plan_api.json").exists()
    assert (PROJECT_ROOT / "results" / "plan_model.json").exists()


def test_run_for_web_api_model_and_report() -> None:
    web_result = PROJECT_ROOT / "results" / "run_web.json"
    api_result = PROJECT_ROOT / "results" / "run_api.json"
    model_result = PROJECT_ROOT / "results" / "run_model.json"
    json_report = PROJECT_ROOT / "results" / "report_latest.json"
    md_report = PROJECT_ROOT / "results" / "report_latest.md"

    _assert_success(_run_cli("run", str(WEB_MANIFEST), "--output", str(web_result)))
    _assert_success(_run_cli("run", str(API_MANIFEST), "--output", str(api_result)))
    _assert_success(_run_cli("run", str(MODEL_MANIFEST), "--output", str(model_result)))

    assert web_result.exists()
    assert api_result.exists()
    assert model_result.exists()

    _assert_success(_run_cli("report", str(model_result), "--output", str(json_report)))
    assert json_report.exists()
    assert md_report.exists()

    report_data = json.loads(json_report.read_text(encoding="utf-8"))
    assert "summary" in report_data
    assert "coverage" in report_data
    assert "recommendation" in report_data
