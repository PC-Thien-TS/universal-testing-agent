from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAG_MANIFEST = PROJECT_ROOT / "manifests" / "samples" / "rag_app_eval.yaml"


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UTA_TIMEOUT_WEB_MS"] = "200"
    env["UTA_TIMEOUT_API_S"] = "1"
    env["UTA_TIMEOUT_MODEL_S"] = "1"
    env["UTA_PROJECTS_DIR"] = str(tmp_path / "projects")
    env["UTA_PROJECT_REGISTRY_FILE"] = str(tmp_path / "projects" / "registry.json")
    env["UTA_RUN_REGISTRY_FILE"] = str(tmp_path / "projects" / "run_registry.json")
    env["UTA_PROJECT_SUMMARY_FILE"] = str(tmp_path / "projects" / "project_summary_latest.json")
    env["UTA_PROJECT_TRENDS_FILE"] = str(tmp_path / "projects" / "project_trends_latest.json")
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _assert_ok(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def test_project_cli_flow_end_to_end(tmp_path: Path) -> None:
    create = _assert_ok(
        _run_cli(
            tmp_path,
            "create-project",
            "--name",
            "sample-rag",
            "--manifest",
            str(RAG_MANIFEST),
            "--type",
            "rag_app",
        )
    )
    assert create["status"] == "created"
    assert create["project"]["project_id"] == "sample-rag"

    listed = _assert_ok(_run_cli(tmp_path, "list-projects"))
    assert any(item["project_id"] == "sample-rag" for item in listed["projects"])

    inspected = _assert_ok(_run_cli(tmp_path, "inspect-project", "sample-rag"))
    assert inspected["project"]["project_id"] == "sample-rag"
    assert "compatibility" in inspected

    run = _assert_ok(_run_cli(tmp_path, "run-project", "sample-rag"))
    assert run["project_id"] == "sample-rag"
    assert Path(run["result_file"]).exists()
    assert Path(run["report_file"]).exists()
    assert "projects" in run["artifact_dir"]
    report_payload = json.loads(Path(run["report_file"]).read_text(encoding="utf-8"))
    assert report_payload["project_id"] == "sample-rag"

    runs = _assert_ok(_run_cli(tmp_path, "list-runs", "sample-rag"))
    assert runs["runs"]

    summary = _assert_ok(_run_cli(tmp_path, "project-summary", "sample-rag"))
    assert summary["project_summary"]["project_id"] == "sample-rag"
    assert summary["project_summary"]["latest_run"] is not None

    trends = _assert_ok(_run_cli(tmp_path, "project-trends", "sample-rag"))
    assert trends["project_trends"]["project_id"] == "sample-rag"

    report = _assert_ok(_run_cli(tmp_path, "report", run["result_file"]))
    assert report["status"] == "reported"
