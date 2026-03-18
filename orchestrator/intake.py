from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.models import IntakeManifest, NormalizedIntake

REQUIRED_SECTIONS: tuple[str, ...] = (
    "project_type",
    "artifacts",
    "environment",
    "request",
    "acceptance",
    "outputs",
)


def load_manifest(manifest_path: str | Path) -> IntakeManifest:
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Manifest must be a YAML object")

    missing = [field for field in REQUIRED_SECTIONS if field not in raw]
    if missing:
        raise ValueError(f"Manifest missing required sections: {', '.join(missing)}")

    return IntakeManifest.model_validate(raw)


def normalize_input(manifest: IntakeManifest, manifest_path: str | Path) -> NormalizedIntake:
    target = (
        manifest.url
        or manifest.environment.get("base_url")
        or manifest.request.get("target")
        or manifest.api.get("base_url")
        or manifest.model.get("endpoint")
    )

    return NormalizedIntake(
        manifest_path=str(Path(manifest_path)),
        name=manifest.name,
        project_type=manifest.project_type,
        url=manifest.url,
        target=target,
        feature=manifest.feature,
        labels=manifest.labels,
        artifacts=manifest.artifacts,
        environment=manifest.environment,
        request=manifest.request,
        acceptance=manifest.acceptance,
        outputs=manifest.outputs,
        auth=manifest.auth,
        constraints=manifest.constraints,
        api=manifest.api,
        model=manifest.model,
    )


def load_and_normalize(manifest_path: str | Path) -> NormalizedIntake:
    manifest = load_manifest(manifest_path)
    return normalize_input(manifest, manifest_path)
