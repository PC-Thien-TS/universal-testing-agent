from pathlib import Path

from orchestrator.models import CoverageStats, DefectSummary, RunRegistryRecord, SummaryStats
from orchestrator.platform_summary import summarize_platform_state
from orchestrator.project_service import default_project_service


def test_project_service_and_platform_summary(tmp_path: Path) -> None:
    project_registry_file = tmp_path / "projects_registry.json"
    run_registry_file = tmp_path / "run_registry.json"
    service = default_project_service(project_registry_file, run_registry_file)

    project = service.create_project_from_manifest(
        name="sample-rag",
        manifest_path="manifests/samples/rag_app_eval.yaml",
        product_type="rag_app",
        project_id="sample-rag",
    )
    assert project.project_id == "sample-rag"

    service.register_run(
        RunRegistryRecord(
            run_id="run-1",
            project_id="sample-rag",
            product_type="rag_app",
            manifest_path="manifests/samples/rag_app_eval.yaml",
            environment_name="default",
            environment_type="local",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:10+00:00",
            status="passed",
            gate_status="pass",
            report_paths={"result_json": "results/projects/sample-rag/latest.json"},
            artifact_dir="results/projects/sample-rag/runs/run-1",
            plugin_used="rag_app",
            summary=SummaryStats(total_checks=3, passed=3, failed=0, blocked=0, skipped=0),
            coverage=CoverageStats(planned_cases=3, executed_cases=3, execution_rate=1.0, requirement_coverage=1.0),
            defects=DefectSummary(),
        )
    )

    summary = service.project_summary("sample-rag")
    assert summary is not None
    assert summary.project_id == "sample-rag"
    assert summary.total_runs == 1

    platform = summarize_platform_state(service)
    assert platform.total_projects == 1
    assert platform.total_runs == 1
