from __future__ import annotations

from orchestrator.models import NormalizedIntake


def classify_product(intake: NormalizedIntake) -> str:
    if intake.url:
        return "web"

    artifact_signals = " ".join(
        " ".join(part for part in [artifact.name, artifact.type, artifact.path, artifact.url] if part)
        for artifact in intake.artifacts
    ).lower()
    if "openapi" in artifact_signals or ".json" in artifact_signals:
        return "api"

    model_endpoint = intake.model.get("endpoint") or intake.request.get("model_endpoint")
    if model_endpoint:
        return "model"

    if intake.project_type in {"web", "api", "model"}:
        return intake.project_type

    return "web"
