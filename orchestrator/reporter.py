from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import ExecutionEnvelope, StandardReport, utc_now_iso
from orchestrator.policy import evaluate_release_policy


def _existing_artifact_references(envelope: ExecutionEnvelope) -> list[str]:
    references = list(envelope.generated_artifacts)
    well_known = [
        Path("results/checklist_latest.json"),
        Path("results/checklist_latest.md"),
        Path("results/testcases_latest.json"),
        Path("results/testcases_latest.md"),
        Path("results/bug_report_template.md"),
        Path("results/generated_assets_latest.json"),
    ]
    for candidate in well_known:
        if candidate.exists():
            references.append(str(candidate))
    return list(dict.fromkeys(references))


def generate_report(envelope: ExecutionEnvelope) -> StandardReport:
    acceptance = envelope.metadata.get("acceptance", {})
    policy = evaluate_release_policy(
        acceptance=acceptance if isinstance(acceptance, dict) else {},
        summary=envelope.summary,
        coverage=envelope.coverage,
        defects=envelope.defects,
    )

    recommendation_notes = list(envelope.recommendation.notes)
    recommendation_notes.extend(policy.reasons)
    recommendation_notes = list(dict.fromkeys(recommendation_notes))

    known_gaps = list(envelope.known_gaps)
    if envelope.summary.blocked > 0:
        known_gaps.append("Blocked checks reduce confidence for release decisions.")
    known_gaps = list(dict.fromkeys(known_gaps))

    assumptions = list(envelope.assumptions)
    assumptions.extend(
        [
            "Policy gate uses manifest acceptance rules when available.",
            "Generated assets are referenced when present in the results directory.",
        ]
    )
    assumptions = list(dict.fromkeys(assumptions))

    artifact_references = _existing_artifact_references(envelope)

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
        recommendation={
            "release_ready": envelope.recommendation.release_ready and policy.release_ready,
            "notes": recommendation_notes,
        },
        policy=policy,
        release_gate_summary="PASS" if policy.release_ready else "FAIL",
        known_gaps=known_gaps,
        assumptions=assumptions,
        artifact_references=artifact_references,
        run_metadata=envelope.run_metadata,
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

## Policy Evaluation
- Verdict: `{report.policy.verdict}`
- Release Ready: `{report.policy.release_ready}`
### Reasons
{_format_list(report.policy.reasons)}

## Release Gate Summary
- Gate: `{report.release_gate_summary}`

## Known Gaps
{_format_list(report.known_gaps)}

## Assumptions
{_format_list(report.assumptions)}

## Generated Artifact References
{_format_list(report.artifact_references)}
"""


def save_markdown_report(report: StandardReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path
