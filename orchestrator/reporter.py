from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import ExecutionEnvelope, StandardReport, utc_now_iso


def generate_report(envelope: ExecutionEnvelope) -> StandardReport:
    execution = envelope.execution
    total_checks = execution.passed + execution.failed
    pass_rate = (execution.passed / total_checks) if total_checks > 0 else 0.0

    summary = {
        "run_id": envelope.run_id,
        "status": envelope.status,
        "adapter": envelope.adapter_name,
        "total_checks": total_checks,
        "passed": execution.passed,
        "failed": execution.failed,
        "defect_count": len(execution.defects),
    }

    coverage = dict(envelope.strategy.coverage)
    coverage["pass_rate"] = round(pass_rate, 4)
    coverage["executed_checks"] = total_checks

    artifacts = [artifact.model_dump(mode="json") for artifact in envelope.intake.artifacts]

    return StandardReport(
        project_type=envelope.project_type,
        artifacts=artifacts,
        environment=envelope.intake.environment,
        request=envelope.intake.request,
        acceptance=envelope.intake.acceptance,
        outputs=envelope.intake.outputs,
        summary=summary,
        defects=execution.defects,
        coverage=coverage,
        metadata={
            "generated_at": utc_now_iso(),
            "manifest_path": envelope.intake.manifest_path,
            "started_at": envelope.started_at,
            "finished_at": envelope.finished_at,
        },
    )


def save_report(report: StandardReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path
