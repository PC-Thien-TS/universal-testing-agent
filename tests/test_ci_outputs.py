from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "data_pipeline_validation.yaml"


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


def test_run_command_ci_mode_emits_sidecar_outputs() -> None:
    proc = _run_cli("run", str(PIPELINE_MANIFEST), "--output", "results/latest_ci_run.json", "--ci")
    assert proc.returncode in {0, 1, 2}, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ci_mode"] is True
    assert payload.get("report_file")
    assert payload.get("ci_summary_file")
    assert payload.get("junit_file")
    assert Path(payload["report_file"]).exists()
    assert Path(payload["ci_summary_file"]).exists()
    assert Path(payload["junit_file"]).exists()


def test_report_command_ci_exit_on_fail_returns_gate_code(tmp_path: Path) -> None:
    run_proc = _run_cli("run", str(PIPELINE_MANIFEST), "--output", str(tmp_path / "base_result.json"))
    assert run_proc.returncode == 0, run_proc.stdout + run_proc.stderr
    base_result = json.loads((tmp_path / "base_result.json").read_text(encoding="utf-8"))
    base_result["quality_gates"] = {
        "gate_status": "fail",
        "gate_reasons": ["simulated fail"],
        "blocking_issues": ["simulated blocking issue"],
        "recommendation": "Do not release",
        "evaluated_rules": {},
    }
    failing_result = tmp_path / "failing_result.json"
    failing_result.write_text(json.dumps(base_result, indent=2), encoding="utf-8")

    report_proc = _run_cli("report", str(failing_result), "--ci", "--exit-on-fail")
    assert report_proc.returncode == 2, report_proc.stdout + report_proc.stderr
    payload = json.loads(report_proc.stdout)
    assert payload["effective_exit_code"] == 2
    assert payload["exit_code"] == 2
