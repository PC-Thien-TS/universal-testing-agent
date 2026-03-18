from __future__ import annotations

from orchestrator.models import NormalizedIntake


def classify_product(intake: NormalizedIntake) -> str:
    explicit_type = (intake.project_type or "").lower()
    if explicit_type in {"web", "api", "model"}:
        return explicit_type

    artifact_signals = " ".join(
        " ".join(part for part in [artifact.name, artifact.type, artifact.path, artifact.url] if part)
        for artifact in intake.artifacts
    ).lower()
    request_signals = " ".join([str(intake.request), str(intake.model), str(intake.api)]).lower()

    api_indicators = ("openapi", "swagger", "paths", ".json", ".yaml", ".yml")
    model_indicators = ("model_endpoint", "labels", "dataset", "evaluation", "metric", "inference", "endpoint")
    web_indicators = ("url", "base_url", "feature", "auth", "booking", "page")

    has_api = any(token in artifact_signals for token in api_indicators) or any(
        token in request_signals for token in api_indicators
    )
    has_model = bool(intake.labels) or any(token in artifact_signals for token in model_indicators) or any(
        token in request_signals for token in model_indicators
    )
    has_web = bool(intake.url) or any(token in request_signals for token in web_indicators) or bool(intake.feature)

    if has_api and not has_model:
        return "api"
    if has_model and not has_api:
        return "model"
    if has_web:
        return "web"
    if has_api:
        return "api"
    if has_model:
        return "model"
    return "web"
