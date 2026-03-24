from pathlib import Path

from orchestrator.models import CoverageStats, DefectSummary, RunRegistryRecord, SummaryStats
from orchestrator.run_registry import add_run_record, latest_run, list_runs, summarize_run_history


def _record(run_id: str, status: str, gate_status: str, started_at: str) -> RunRegistryRecord:
    return RunRegistryRecord(
        run_id=run_id,
        project_id="sample-rag",
        product_type="rag_app",
        manifest_path="manifests/samples/rag_app_eval.yaml",
        environment_name="default",
        environment_type="local",
        started_at=started_at,
        finished_at=started_at,
        status=status,
        gate_status=gate_status,
        report_paths={"result_json": f"results/{run_id}.json"},
        artifact_dir=f"results/projects/sample-rag/runs/{run_id}",
        plugin_used="rag_app",
        summary=SummaryStats(total_checks=2, passed=1 if status == "passed" else 0, failed=0 if status == "passed" else 1, blocked=0, skipped=0),
        coverage=CoverageStats(planned_cases=2, executed_cases=2, execution_rate=1.0, requirement_coverage=0.8),
        defects=DefectSummary(),
    )


def test_run_registry_add_list_latest_and_summary(tmp_path: Path) -> None:
    run_registry_file = tmp_path / "run_registry.json"
    add_run_record(run_registry_file, _record("r1", "failed", "fail", "2026-01-01T00:00:00+00:00"))
    add_run_record(run_registry_file, _record("r2", "passed", "pass", "2026-01-02T00:00:00+00:00"))

    runs = list_runs(run_registry_file, "sample-rag")
    assert len(runs) == 2
    assert runs[0].run_id == "r2"

    latest = latest_run(run_registry_file, "sample-rag")
    assert latest is not None
    assert latest.run_id == "r2"

    summary = summarize_run_history(run_registry_file, "sample-rag")
    assert summary["total_runs"] == 2
    assert summary["latest_status"] == "passed"
