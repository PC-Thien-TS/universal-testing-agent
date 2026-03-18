from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import ExecutionEnvelope, StandardReport, utc_now_iso


def generate_report(envelope: ExecutionEnvelope) -> StandardReport:
    return StandardReport(
        run_id=envelope.run_id,
        project_name=envelope.project_name,
        project_type=envelope.project_type,
        adapter=envelope.adapter,
        status=envelope.status,
        started_at=envelope.started_at,
        finished_at=envelope.finished_at,
        duration_seconds=envelope.duration_seconds,
        summary=envelope.summary,
        coverage=envelope.coverage,
        defects=envelope.defects,
        evidence=envelope.evidence,
        recommendation=envelope.recommendation,
        generated_at=utc_now_iso(),
    )


def save_report(report: StandardReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


def _format_list(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def render_markdown_report(report: StandardReport) -> str:
    return f"""# Universal Testing Agent Report

## Project Summary
- Run ID: `{report.run_id}`
- Project: `{report.project_name}`
- Project Type: `{report.project_type}`
- Adapter: `{report.adapter}`
- Status: `{report.status}`
- Started: `{report.started_at}`
- Finished: `{report.finished_at}`
- Duration (s): `{report.duration_seconds}`

## Execution Summary
- Total Checks: `{report.summary.total_checks}`
- Passed: `{report.summary.passed}`
- Failed: `{report.summary.failed}`
- Blocked: `{report.summary.blocked}`
- Skipped: `{report.summary.skipped}`
- Planned Cases: `{report.coverage.planned_cases}`
- Executed Cases: `{report.coverage.executed_cases}`
- Execution Rate: `{report.coverage.execution_rate}`
- Requirement Coverage: `{report.coverage.requirement_coverage}`

## Defects
- Blocker: `{report.defects.blocker}`
- Critical: `{report.defects.critical}`
- High: `{report.defects.high}`
- Medium: `{report.defects.medium}`
- Low: `{report.defects.low}`

## Evidence
### Logs
{_format_list(report.evidence.logs)}

### Screenshots
{_format_list(report.evidence.screenshots)}

### Traces
{_format_list(report.evidence.traces)}

### Artifacts
{_format_list(report.evidence.artifacts)}

## Release Recommendation
- Release Ready: `{report.recommendation.release_ready}`
### Notes
{_format_list(report.recommendation.notes)}
"""


def save_markdown_report(report: StandardReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path
