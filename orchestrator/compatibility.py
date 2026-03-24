from __future__ import annotations

from typing import Any

from orchestrator.models import ProjectCompatibilitySummary, ProjectRecord
from orchestrator.registry import get_registry
from orchestrator.taxonomy import get_taxonomy_profile


def analyze_project_compatibility(project: ProjectRecord, *, environment_name: str | None = None) -> ProjectCompatibilitySummary:
    registry = get_registry()
    inspection = registry.inspection_for_product_type(project.product_type)
    taxonomy = get_taxonomy_profile(project.product_type)
    supported_capabilities = set(inspection.plugin.supported_capabilities)
    required_capabilities = list(taxonomy.capability_expectations)
    missing = [capability for capability in required_capabilities if capability not in supported_capabilities]

    environment_notes: list[str] = []
    if environment_name:
        environment = project.environments.get(environment_name, {})
        if environment:
            if environment.get("type"):
                environment_notes.append(f"Environment '{environment_name}' type={environment.get('type')}.")
            if environment.get("base_url"):
                environment_notes.append("Environment provides base_url.")
            else:
                environment_notes.append("Environment base_url is empty; smoke fallbacks may be used.")
        else:
            environment_notes.append(f"Environment '{environment_name}' is not configured; using manifest defaults.")

    return ProjectCompatibilitySummary(
        project_id=project.project_id,
        product_type=project.product_type,
        plugin_name=inspection.plugin.plugin_name,
        plugin_version=inspection.plugin.plugin_version,
        support_level=inspection.validation.support_level,
        fallback_mode=registry.fallback_mode_for(project.product_type),
        supports_required_capabilities=len(missing) == 0,
        missing_capabilities=missing,
        fallback_only=inspection.validation.support_level == "fallback_only",
        missing_recommended_capabilities=list(inspection.validation.missing_recommended_capabilities),
        environment_notes=environment_notes,
    )


def plugin_compatibility_payload(project: ProjectRecord, *, environment_name: str | None = None) -> dict[str, Any]:
    return analyze_project_compatibility(project, environment_name=environment_name).model_dump(mode="json")

