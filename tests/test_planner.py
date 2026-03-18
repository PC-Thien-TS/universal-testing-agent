from orchestrator.models import NormalizedIntake
from orchestrator.planner import generate_test_strategy


def test_planner_returns_scope_risks_coverage() -> None:
    intake = NormalizedIntake(
        manifest_path="sample.yaml",
        name="sample",
        project_type="web",
        url="https://example.com",
        target="https://example.com",
        feature="booking",
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

    plan = generate_test_strategy(intake, "web")
    assert isinstance(plan.scope, list)
    assert isinstance(plan.risks, list)
    assert isinstance(plan.coverage, dict)
    assert "type" in plan.coverage
