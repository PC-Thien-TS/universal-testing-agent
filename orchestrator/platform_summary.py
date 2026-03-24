from __future__ import annotations

from typing import Any

from orchestrator.models import PlatformStateSummary, ProjectRunSummary, utc_now_iso
from orchestrator.project_service import ProjectService


def list_project_summaries(service: ProjectService) -> list[ProjectRunSummary]:
    summaries: list[ProjectRunSummary] = []
    for project in service.list_projects(active_only=False):
        summary = service.project_summary(project.project_id)
        if summary is not None:
            summaries.append(summary)
    return sorted(summaries, key=lambda item: item.project_id)


def aggregate_latest_status_per_project(service: ProjectService) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for summary in list_project_summaries(service):
        latest = summary.latest_run
        payload.append(
            {
                "project_id": summary.project_id,
                "project_name": summary.project_name,
                "product_type": summary.product_type,
                "latest_status": latest.status if latest else None,
                "latest_gate_status": latest.gate_status if latest else None,
                "total_runs": summary.total_runs,
                "trend": summary.trend,
                "flaky_summary": summary.flaky_summary,
            }
        )
    return payload


def summarize_platform_state(service: ProjectService) -> PlatformStateSummary:
    summaries = list_project_summaries(service)
    total_projects = len(summaries)
    active_projects = len([project for project in service.list_projects(active_only=True)])
    total_runs = sum(item.total_runs for item in summaries)
    pass_rate = round(sum(item.pass_rate for item in summaries) / max(total_projects, 1), 4) if summaries else 0.0
    gate_pass_rate = (
        round(sum(item.gate_pass_rate for item in summaries) / max(total_projects, 1), 4) if summaries else 0.0
    )
    return PlatformStateSummary(
        generated_at=utc_now_iso(),
        total_projects=total_projects,
        active_projects=active_projects,
        total_runs=total_runs,
        pass_rate=pass_rate,
        gate_pass_rate=gate_pass_rate,
        projects=summaries,
    )

