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
        labels=[],
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
    assert plan.execution_priorities


def test_api_plan_includes_endpoint_matrix() -> None:
    intake = NormalizedIntake(
        manifest_path="sample.yaml",
        name="api-sample",
        project_type="api",
        labels=[],
        artifacts=[],
        environment={},
        request={"endpoints": ["/health"]},
        acceptance={},
        outputs={},
        auth={},
        constraints=[],
        api={"base_url": ""},
        model={},
    )
    plan = generate_test_strategy(intake, "api")
    assert plan.endpoint_matrix_summary


def test_model_plan_includes_metrics() -> None:
    intake = NormalizedIntake(
        manifest_path="sample.yaml",
        name="model-sample",
        project_type="model",
        labels=["safe"],
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
    plan = generate_test_strategy(intake, "model")
    assert plan.evaluation_dimensions
    assert plan.metrics_to_compute
