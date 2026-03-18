from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from adapters.base import BaseAdapter
from orchestrator.models import (
    AdapterPlan,
    Defect,
    DiscoveryResult,
    EvidenceBundle,
    ExecutionEnvelope,
    ExecutionResult,
    GeneratedAssets,
    NormalizedIntake,
    StrategyPlan,
    utc_now_iso,
)


def execute_pipeline(
    intake: NormalizedIntake,
    product_type: str,
    strategy: StrategyPlan,
    adapter: BaseAdapter,
) -> ExecutionEnvelope:
    run_id = str(uuid4())
    started_at = utc_now_iso()

    discovery = DiscoveryResult()
    adapter_plan = AdapterPlan()
    generated_assets = GeneratedAssets()
    execution = ExecutionResult(status="failed", passed=0, failed=1)
    evidence = EvidenceBundle(notes=["No evidence generated."])
    status = "failed"

    try:
        discovery = adapter.discover(intake)
        adapter_plan = adapter.plan(intake, strategy)
        generated_assets = adapter.generate_assets(intake, adapter_plan)
        execution = adapter.execute(intake, generated_assets)
        evidence = adapter.collect_evidence(intake, execution)
        status = "passed" if execution.status == "passed" else "failed"
    except Exception as exc:  # pragma: no cover - protective fallback
        execution = ExecutionResult(
            status="error",
            passed=0,
            failed=1,
            defects=[
                Defect(
                    id="executor.unhandled",
                    severity="critical",
                    message=str(exc),
                    details={"exception_type": type(exc).__name__},
                )
            ],
            raw_output={},
        )
        evidence = EvidenceBundle(files=[], notes=["Execution aborted due to unhandled exception."])
        status = "error"

    return ExecutionEnvelope(
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now_iso(),
        project_type=product_type,
        intake=intake,
        strategy=strategy,
        adapter_name=adapter.name,
        discovery=discovery,
        adapter_plan=adapter_plan,
        generated_assets=generated_assets,
        execution=execution,
        evidence=evidence,
        status=status,
    )


def save_execution_result(envelope: ExecutionEnvelope, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


def load_execution_result(result_path: str | Path) -> ExecutionEnvelope:
    raw = json.loads(Path(result_path).read_text(encoding="utf-8"))
    return ExecutionEnvelope.model_validate(raw)
