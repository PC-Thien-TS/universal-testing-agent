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
from runners.playwright_runner import run_web_smoke


class WebAdapter(BaseAdapter):
    name = "web"

    def discover(self, intake: NormalizedIntake) -> DiscoveryResult:
        return DiscoveryResult(items=[intake.target or ""], metadata={"adapter": self.name})

    def plan(self, intake: NormalizedIntake, strategy: StrategyPlan) -> AdapterPlan:
        steps = [
            "Navigate to target URL",
            "Validate HTTP response",
            "Verify auth selector when required",
            "Capture screenshot evidence",
        ]
        return AdapterPlan(steps=steps, coverage=strategy.coverage, metadata={"feature": intake.feature})

    def generate_assets(self, intake: NormalizedIntake, adapter_plan: AdapterPlan) -> GeneratedAssets:
        return GeneratedAssets(artifacts=["web-smoke-run"], metadata={"step_count": len(adapter_plan.steps)})

    def execute(self, intake: NormalizedIntake, generated_assets: GeneratedAssets) -> ExecutionResult:
        runner_result = run_web_smoke(
            url=intake.target or "",
            auth=intake.auth,
            timeout_ms=self.config.timeouts.web_ms,
            screenshot_dir=self.config.paths.evidence_dir,
            browser=self.config.runners.web.browser,
            headless=self.config.runners.web.headless,
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
        screenshot = execution_result.raw_output.get("screenshot")
        if screenshot:
            files.append(str(screenshot))
        else:
            notes.append("No screenshot captured.")
        notes.append(f"Execution status: {execution_result.status}")
        return EvidenceBundle(files=files, notes=notes)
