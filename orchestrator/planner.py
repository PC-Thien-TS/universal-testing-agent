from __future__ import annotations

from pathlib import Path

from orchestrator.models import NormalizedIntake, StrategyPlan


def generate_test_strategy(intake: NormalizedIntake, product_type: str) -> StrategyPlan:
    scope: list[str] = []
    if intake.feature:
        scope.append(f"Feature: {intake.feature}")
    if intake.target:
        scope.append(f"Primary target: {intake.target}")
    if intake.artifacts:
        scope.append(f"Artifacts covered: {len(intake.artifacts)}")

    default_risks: dict[str, list[str]] = {
        "web": [
            "Critical page unreachable",
            "Auth-gated paths inaccessible",
            "Core feature interactions regress",
        ],
        "api": [
            "Endpoint availability regressions",
            "Schema drift from contract",
            "5xx stability issues",
        ],
        "model": [
            "Output quality below threshold",
            "Latency exceeds acceptance",
            "Unexpected output format",
        ],
    }

    coverage = {
        "type": product_type,
        "functional": "basic",
        "negative": "basic",
        "constraints": intake.constraints,
        "acceptance": intake.acceptance,
        "prompt_source": str(Path("prompts/strategy_prompt.txt")),
    }

    return StrategyPlan(scope=scope, risks=default_risks.get(product_type, []), coverage=coverage)
