from orchestrator.models import (
    AdapterPlan,
    DiscoveryResult,
    EvidenceBundle,
    ExecutionEnvelope,
    ExecutionResult,
    GeneratedAssets,
    NormalizedIntake,
    StrategyPlan,
)
from orchestrator.reporter import generate_report


def test_reporter_contains_summary_defects_coverage() -> None:
    intake = NormalizedIntake(
        manifest_path="manifests/samples/web_booking.yaml",
        name="web-booking-demo",
        project_type="web",
        url="https://example.com",
        target="https://example.com",
        artifacts=[],
        environment={},
        request={},
        acceptance={},
        outputs={},
        auth={},
        constraints=[],
        api={},
        model={},
    )
    envelope = ExecutionEnvelope(
        run_id="run-1",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_type="web",
        intake=intake,
        strategy=StrategyPlan(scope=["x"], risks=["y"], coverage={"type": "web"}),
        adapter_name="web",
        discovery=DiscoveryResult(items=[], metadata={}),
        adapter_plan=AdapterPlan(steps=[], coverage={}, metadata={}),
        generated_assets=GeneratedAssets(artifacts=[], metadata={}),
        execution=ExecutionResult(status="passed", passed=2, failed=0, defects=[], raw_output={}),
        evidence=EvidenceBundle(files=[], notes=[]),
        status="passed",
    )

    report = generate_report(envelope)
    assert "total_checks" in report.summary
    assert isinstance(report.defects, list)
    assert "pass_rate" in report.coverage
