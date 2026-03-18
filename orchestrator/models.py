from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UtaModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Artifact(UtaModel):
    name: str = "artifact"
    type: str = "generic"
    path: str | None = None
    url: str | None = None


class IntakeManifest(UtaModel):
    name: str = "unnamed-project"
    project_type: str = "auto"
    url: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    feature: str | None = None
    constraints: list[str] | dict[str, Any] = Field(default_factory=list)
    api: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)


class NormalizedIntake(UtaModel):
    manifest_path: str
    name: str
    project_type: str
    url: str | None = None
    target: str | None = None
    feature: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] | dict[str, Any] = Field(default_factory=list)
    api: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)


class StrategyPlan(UtaModel):
    scope: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(UtaModel):
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterPlan(UtaModel):
    steps: list[str] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratedAssets(UtaModel):
    artifacts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Defect(UtaModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(UtaModel):
    status: Literal["passed", "failed", "error"] = "failed"
    passed: int = 0
    failed: int = 0
    defects: list[Defect] = Field(default_factory=list)
    raw_output: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(UtaModel):
    files: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExecutionEnvelope(UtaModel):
    run_id: str
    started_at: str
    finished_at: str | None = None
    project_type: str
    intake: NormalizedIntake
    strategy: StrategyPlan
    adapter_name: str
    discovery: DiscoveryResult
    adapter_plan: AdapterPlan
    generated_assets: GeneratedAssets
    execution: ExecutionResult
    evidence: EvidenceBundle
    status: Literal["passed", "failed", "error"]


class StandardReport(UtaModel):
    project_type: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    defects: list[Defect] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
