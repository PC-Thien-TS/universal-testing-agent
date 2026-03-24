from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orchestrator.compatibility import analyze_project_compatibility
from orchestrator.history_analyzer import analyze_history_intelligence
from orchestrator.intake import load_manifest
from orchestrator.models import (
    CoverageStats,
    DefectSummary,
    HistoryRecord,
    ProjectRecord,
    ProjectRunSummary,
    RunRegistryRecord,
    SummaryStats,
)
from orchestrator.project_registry import create_project, get_project, list_projects
from orchestrator.run_registry import add_run_record, latest_run, list_runs, summarize_run_history
from orchestrator.trends import analyze_trends


def _to_history_record(project: ProjectRecord, run: RunRegistryRecord) -> HistoryRecord:
    return HistoryRecord(
        run_id=run.run_id,
        timestamp=run.finished_at,
        project_name=project.name,
        project_type=run.product_type,
        adapter=run.plugin_used or run.product_type,
        status=run.status,
        gate_status=run.gate_status,
        environment_type=run.environment_type,
        summary=run.summary if isinstance(run.summary, SummaryStats) else SummaryStats.model_validate(run.summary),
        coverage=run.coverage if isinstance(run.coverage, CoverageStats) else CoverageStats.model_validate(run.coverage),
        defects=run.defects if isinstance(run.defects, DefectSummary) else DefectSummary.model_validate(run.defects),
        release_ready=(run.gate_status == "pass"),
    )


@dataclass
class ProjectService:
    project_registry_path: str
    run_registry_path: str

    def create_project_from_manifest(
        self,
        *,
        name: str,
        manifest_path: str,
        product_type: str | None = None,
        project_id: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        environments: dict[str, dict[str, Any]] | None = None,
        active: bool = True,
    ) -> ProjectRecord:
        manifest = load_manifest(manifest_path)
        resolved_type = (product_type or manifest.project_type).strip()
        if environments is not None:
            resolved_envs = environments
        else:
            if hasattr(manifest.environment, "model_dump"):
                default_env = manifest.environment.model_dump(mode="json")
            elif isinstance(manifest.environment, dict):
                default_env = dict(manifest.environment)
            else:
                default_env = {}
            resolved_envs = {"default": default_env}
        return create_project(
            self.project_registry_path,
            name=name,
            product_type=resolved_type,
            default_manifest_path=manifest_path,
            project_id=project_id,
            description=description,
            tags=tags or [],
            environments=resolved_envs,
            active=active,
        )

    def list_projects(self, *, active_only: bool = False) -> list[ProjectRecord]:
        return list_projects(self.project_registry_path, active_only=active_only)

    def inspect_project(self, project_id: str) -> ProjectRecord | None:
        return get_project(self.project_registry_path, project_id)

    def register_run(self, run: RunRegistryRecord) -> RunRegistryRecord:
        return add_run_record(self.run_registry_path, run)

    def list_runs(self, project_id: str, *, limit: int | None = None) -> list[RunRegistryRecord]:
        return list_runs(self.run_registry_path, project_id, limit=limit)

    def latest_run(self, project_id: str) -> RunRegistryRecord | None:
        return latest_run(self.run_registry_path, project_id)

    def project_summary(self, project_id: str) -> ProjectRunSummary | None:
        project = self.inspect_project(project_id)
        if project is None:
            return None

        runs = self.list_runs(project_id)
        latest = runs[0] if runs else None
        history_records = [_to_history_record(project, run) for run in runs]
        trends = analyze_trends(history_records)
        intelligence = analyze_history_intelligence(history_records)
        rollup = summarize_run_history(self.run_registry_path, project_id)
        compatibility = analyze_project_compatibility(project, environment_name="default")

        return ProjectRunSummary(
            project_id=project.project_id,
            project_name=project.name,
            product_type=project.product_type,
            total_runs=int(rollup.get("total_runs", 0)),
            latest_run=latest,
            pass_rate=float(rollup.get("pass_rate", 0.0)),
            gate_pass_rate=float(rollup.get("gate_pass_rate", 0.0)),
            trend=trends.overall_direction,
            flaky_summary=intelligence.flaky_classification,
            compatibility=compatibility,
        )

    def project_trends(self, project_id: str) -> dict[str, Any] | None:
        project = self.inspect_project(project_id)
        if project is None:
            return None
        runs = self.list_runs(project_id)
        history_records = [_to_history_record(project, run) for run in runs]
        trends = analyze_trends(history_records)
        intelligence = analyze_history_intelligence(history_records)
        return {
            "project_id": project_id,
            "runs_analyzed": trends.runs_analyzed,
            "trend_summary": trends.model_dump(mode="json"),
            "history_intelligence": intelligence.model_dump(mode="json"),
        }


def default_project_service(project_registry_path: str | Path, run_registry_path: str | Path) -> ProjectService:
    return ProjectService(project_registry_path=str(project_registry_path), run_registry_path=str(run_registry_path))
