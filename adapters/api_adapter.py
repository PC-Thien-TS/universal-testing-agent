from __future__ import annotations

from adapters.base import BaseAdapter
from orchestrator.models import (
    AdapterPlan,
    Defect,
    DiscoveryResult,
    EvidenceBundle,
    ExecutionResult,
    GeneratedAssets,
    NormalizedIntake,
    StrategyPlan,
)
from runners.pytest_runner import run_api_pytest


class ApiAdapter(BaseAdapter):
    name = "api"

    def discover(self, intake: NormalizedIntake) -> DiscoveryResult:
        base_url = intake.api.get("base_url") or intake.target or ""
        endpoints = intake.request.get("endpoints", [])
        return DiscoveryResult(items=[base_url, *[str(endpoint) for endpoint in endpoints]], metadata={"adapter": self.name})

    def plan(self, intake: NormalizedIntake, strategy: StrategyPlan) -> AdapterPlan:
        steps = [
            "Resolve API base URL",
            "Generate temporary pytest smoke test",
            "Execute pytest against configured endpoints",
            "Collect pytest logs as evidence",
        ]
        return AdapterPlan(steps=steps, coverage=strategy.coverage, metadata={"feature": intake.feature})

    def generate_assets(self, intake: NormalizedIntake, adapter_plan: AdapterPlan) -> GeneratedAssets:
        endpoints = intake.request.get("endpoints", ["/"])
        return GeneratedAssets(
            artifacts=["api-smoke-pytest"],
            metadata={"endpoint_count": len(endpoints), "step_count": len(adapter_plan.steps)},
        )

    def execute(self, intake: NormalizedIntake, generated_assets: GeneratedAssets) -> ExecutionResult:
        base_url = intake.api.get("base_url") or intake.target or ""
        endpoints = intake.request.get("endpoints", ["/"])
        runner_result = run_api_pytest(
            base_url=base_url,
            endpoints=endpoints,
            timeout_s=self.config.timeouts.api_s,
            pytest_args=self.config.runners.api.pytest_args,
        )
        defects = [Defect.model_validate(item) for item in runner_result.get("defects", [])]
        return ExecutionResult(
            status=runner_result.get("status", "failed"),
            passed=int(runner_result.get("passed", 0)),
            failed=int(runner_result.get("failed", 0)),
            defects=defects,
            raw_output=runner_result.get("raw_output", {}),
        )

    def collect_evidence(self, intake: NormalizedIntake, execution_result: ExecutionResult) -> EvidenceBundle:
        files: list[str] = []
        notes: list[str] = []
        if temp_test := execution_result.raw_output.get("test_file"):
            files.append(str(temp_test))
        notes.append("Pytest stdout and stderr captured in raw_output.")
        return EvidenceBundle(files=files, notes=notes)
