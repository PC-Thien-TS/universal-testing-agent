from __future__ import annotations

from orchestrator.models import NormalizedIntake, StrategyPlan


def _as_constraints(value: list[str] | dict[str, object]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [f"{key}: {value[key]}" for key in value]


def _build_web_plan(intake: NormalizedIntake) -> StrategyPlan:
    scope = [
        "Landing page and critical routes",
        f"Feature focus: {intake.feature or 'primary workflow'}",
        f"Target URL: {intake.target or intake.url or 'n/a'}",
    ]
    risks = [
        "Target URL unreachable or unstable",
        "Authentication path blocks required flow",
        "Feature-level regressions in core navigation",
    ]
    coverage = {
        "functional": "smoke",
        "auth": "basic",
        "negative": "basic",
    }
    execution_priorities = [
        "P0: URL/route reachability",
        "P1: Auth gate expectations",
        "P2: Feature workflow smoke",
    ]
    constraints = _as_constraints(intake.constraints)
    return StrategyPlan(
        scope=scope,
        risks=risks,
        coverage=coverage,
        execution_priorities=execution_priorities,
        constraints=constraints,
    )


def _build_api_plan(intake: NormalizedIntake) -> StrategyPlan:
    endpoints = intake.request.get("endpoints", ["/"])
    endpoint_matrix_summary = [
        {"endpoint": str(endpoint), "method": "GET", "checks": ["status", "basic payload shape"]}
        for endpoint in endpoints
    ]
    scope = [
        "API reachability and contract smoke checks",
        f"Base target: {intake.api.get('base_url') or intake.target or 'simulation'}",
    ]
    risks = [
        "Unexpected 5xx status codes",
        "Payload shape drift from API contract",
        "Authentication misconfiguration",
    ]
    coverage = {
        "auth_coverage": "basic",
        "contract_coverage": "smoke",
        "negative_coverage": "basic",
    }
    return StrategyPlan(
        scope=scope,
        risks=risks,
        coverage=coverage,
        execution_priorities=["P0: endpoint availability", "P1: status/code consistency", "P2: payload checks"],
        constraints=_as_constraints(intake.constraints),
        endpoint_matrix_summary=endpoint_matrix_summary,
    )


def _build_model_plan(intake: NormalizedIntake) -> StrategyPlan:
    evaluation_dimensions = [
        "Label alignment",
        "Response format consistency",
        "Threshold conformance",
    ]
    metrics_to_compute = [
        "label_coverage",
        "sample_count",
        "quality_score_proxy",
    ]
    threshold = float(intake.acceptance.get("quality_threshold", 0.7))
    threshold_notes = [
        f"Quality threshold target: {threshold}",
        "Missing endpoint will use deterministic local evaluation fallback",
    ]
    scope = [
        "Model metadata and dataset readiness",
        "Evaluation-case processing",
    ]
    risks = [
        "Insufficient sample metadata",
        "Threshold misses on expected labels",
        "Endpoint unavailability for live inference",
    ]
    coverage = {
        "dimensions": "metadata+smoke",
        "metrics": metrics_to_compute,
        "threshold": threshold,
    }
    return StrategyPlan(
        scope=scope,
        risks=risks,
        coverage=coverage,
        execution_priorities=["P0: dataset/labels inspection", "P1: metric computation", "P2: endpoint smoke if provided"],
        constraints=_as_constraints(intake.constraints),
        evaluation_dimensions=evaluation_dimensions,
        metrics_to_compute=metrics_to_compute,
        threshold_risk_notes=threshold_notes,
    )


def generate_test_strategy(intake: NormalizedIntake, product_type: str) -> StrategyPlan:
    if product_type == "api":
        return _build_api_plan(intake)
    if product_type == "model":
        return _build_model_plan(intake)
    return _build_web_plan(intake)
