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
RUNS_DIR = PROJECT_ROOT / "results" / "runs"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UTA_TIMEOUT_WEB_MS"] = "200"
    env["UTA_TIMEOUT_API_S"] = "1"
    env["UTA_TIMEOUT_MODEL_S"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _assert_success(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def _assert_observability_payload(payload: dict) -> None:
    assert payload.get("run_id")
    artifact_dir = payload.get("artifact_dir")
    assert artifact_dir
    metadata = Path(artifact_dir) / "metadata.json"
    run_log = Path(artifact_dir) / "run.log"
    assert metadata.exists()
    assert run_log.exists()


def test_validate_manifest_for_web_api_model() -> None:
    web = _assert_success(_run_cli("validate-manifest", str(WEB_MANIFEST)))
    api = _assert_success(_run_cli("validate-manifest", str(API_MANIFEST)))
    model = _assert_success(_run_cli("validate-manifest", str(MODEL_MANIFEST)))
    _assert_observability_payload(web)
    _assert_observability_payload(api)
    _assert_observability_payload(model)


def test_plan_for_web_api_model() -> None:
    web = _assert_success(_run_cli("plan", str(WEB_MANIFEST), "--output", "results/plan_web.json"))
    api = _assert_success(_run_cli("plan", str(API_MANIFEST), "--output", "results/plan_api.json"))
    model = _assert_success(_run_cli("plan", str(MODEL_MANIFEST), "--output", "results/plan_model.json"))
    _assert_observability_payload(web)
    _assert_observability_payload(api)
    _assert_observability_payload(model)
    assert (PROJECT_ROOT / "results" / "plan_web.json").exists()
    assert (PROJECT_ROOT / "results" / "plan_api.json").exists()
    assert (PROJECT_ROOT / "results" / "plan_model.json").exists()


def test_generate_assets_command_outputs_expected_files() -> None:
    payload = _assert_success(_run_cli("generate-assets", str(WEB_MANIFEST)))
    _assert_observability_payload(payload)
    expected_files = [
        PROJECT_ROOT / "results" / "checklist_latest.json",
        PROJECT_ROOT / "results" / "checklist_latest.md",
        PROJECT_ROOT / "results" / "testcases_latest.json",
        PROJECT_ROOT / "results" / "testcases_latest.md",
        PROJECT_ROOT / "results" / "bug_report_template.md",
    ]
    for file_path in expected_files:
        assert file_path.exists()


def test_run_for_web_api_model_and_report_with_policy() -> None:
    web_result = PROJECT_ROOT / "results" / "run_web.json"
    api_result = PROJECT_ROOT / "results" / "run_api.json"
    model_result = PROJECT_ROOT / "results" / "run_model.json"
    json_report = PROJECT_ROOT / "results" / "report_latest.json"
    md_report = PROJECT_ROOT / "results" / "report_latest.md"

    web_payload = _assert_success(_run_cli("run", str(WEB_MANIFEST), "--output", str(web_result)))
    api_payload = _assert_success(_run_cli("run", str(API_MANIFEST), "--output", str(api_result)))
    model_payload = _assert_success(_run_cli("run", str(MODEL_MANIFEST), "--output", str(model_result)))
    _assert_observability_payload(web_payload)
    _assert_observability_payload(api_payload)
    _assert_observability_payload(model_payload)

    assert web_result.exists()
    assert api_result.exists()
    assert model_result.exists()

    report_payload = _assert_success(_run_cli("report", str(model_result), "--output", str(json_report)))
    _assert_observability_payload(report_payload)
    assert json_report.exists()
    assert md_report.exists()

    report_data = json.loads(json_report.read_text(encoding="utf-8"))
    assert "summary" in report_data
    assert "coverage" in report_data
    assert "recommendation" in report_data
    assert "policy" in report_data
    assert "release_gate_summary" in report_data
    assert "artifact_references" in report_data


def test_runs_artifact_directory_is_created() -> None:
    payload = _assert_success(_run_cli("validate-manifest", str(WEB_MANIFEST)))
    _assert_observability_payload(payload)
    assert RUNS_DIR.exists()
    assert any(child.is_dir() for child in RUNS_DIR.iterdir())
