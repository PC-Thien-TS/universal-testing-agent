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
    labels: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntakeManifest(UtaModel):
    name: str = "unnamed-project"
    project_type: str = "auto"
    url: str | None = None
    labels: list[str] = Field(default_factory=list)
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
    labels: list[str] = Field(default_factory=list)
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
    execution_priorities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    endpoint_matrix_summary: list[dict[str, Any]] = Field(default_factory=list)
    evaluation_dimensions: list[str] = Field(default_factory=list)
    metrics_to_compute: list[str] = Field(default_factory=list)
    threshold_risk_notes: list[str] = Field(default_factory=list)


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


class SummaryStats(UtaModel):
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0


class CoverageStats(UtaModel):
    planned_cases: int = 0
    executed_cases: int = 0
    execution_rate: float = 0.0
    requirement_coverage: float = 0.0


class DefectDetail(UtaModel):
    id: str
    severity: Literal["blocker", "critical", "high", "medium", "low"] = "medium"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DefectSummary(UtaModel):
    blocker: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class EvidenceBundle(UtaModel):
    logs: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    traces: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


class Recommendation(UtaModel):
    release_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class ExecutionResult(UtaModel):
    status: Literal["passed", "failed", "blocked", "error"] = "blocked"
    summary: SummaryStats = Field(default_factory=SummaryStats)
    coverage: CoverageStats = Field(default_factory=CoverageStats)
    defect_details: list[DefectDetail] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    recommendation_notes: list[str] = Field(default_factory=list)
    raw_output: dict[str, Any] = Field(default_factory=dict)


class ExecutionEnvelope(UtaModel):
    run_id: str
    project_name: str
    project_type: str
    adapter: str
    status: Literal["passed", "failed", "blocked", "error"]
    started_at: str
    finished_at: str
    duration_seconds: float
    summary: SummaryStats
    coverage: CoverageStats
    defects: DefectSummary
    evidence: EvidenceBundle
    recommendation: Recommendation
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_output: dict[str, Any] = Field(default_factory=dict)


class StandardReport(UtaModel):
    run_id: str
    project_name: str
    project_type: str
    adapter: str
    status: Literal["passed", "failed", "blocked", "error"]
    started_at: str
    finished_at: str
    duration_seconds: float
    summary: SummaryStats
    coverage: CoverageStats
    defects: DefectSummary
    evidence: EvidenceBundle
    recommendation: Recommendation
    generated_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def defect_summary_from_details(defects: list[DefectDetail]) -> DefectSummary:
    counters = DefectSummary()
    for defect in defects:
        counters_value = getattr(counters, defect.severity)
        setattr(counters, defect.severity, counters_value + 1)
    return counters


def status_from_summary(summary: SummaryStats) -> Literal["passed", "failed", "blocked", "error"]:
    if summary.failed > 0:
        return "failed"
    if summary.blocked > 0:
        return "blocked"
    return "passed"
