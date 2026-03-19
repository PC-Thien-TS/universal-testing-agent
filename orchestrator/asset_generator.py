from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.config import RuntimeConfig
from orchestrator.models import NormalizedIntake, StrategyPlan


class GeneratedAssetBundle(BaseModel):
    project_type: str
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    testcases: list[dict[str, Any]] = Field(default_factory=list)
    known_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)


def _web_assets(intake: NormalizedIntake, strategy: StrategyPlan) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    checklist = [
        {"id": "WEB-CHK-001", "item": "Target URL is configured", "priority": "P0"},
        {"id": "WEB-CHK-002", "item": "Auth expectation is defined", "priority": "P1"},
        {"id": "WEB-CHK-003", "item": "Feature route is reachable", "priority": "P1"},
    ]
    testcases = [
        {
            "id": "WEB-TC-001",
            "title": "Open primary web target",
            "type": "smoke",
            "steps": [f"Navigate to {intake.target or intake.url or '[target]'}", "Capture status and page evidence"],
            "expected": "Status below 400 and evidence traces generated",
        },
        {
            "id": "WEB-TC-002",
            "title": f"Validate feature workflow ({intake.feature or 'primary'})",
            "type": "functional",
            "steps": ["Open feature entry route", "Verify minimal flow interactions"],
            "expected": "No blocking issues in core workflow",
        },
    ]
    known_gaps = ["No deep browser interaction assertions in smoke-generated assets."]
    assumptions = [f"Strategy priorities used: {', '.join(strategy.execution_priorities) or 'default'}"]
    return checklist, testcases, known_gaps, assumptions


def _api_assets(intake: NormalizedIntake, strategy: StrategyPlan) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    endpoints = intake.request.get("endpoints", ["/"])
    checklist = [
        {"id": "API-CHK-001", "item": "Base URL or simulation mode defined", "priority": "P0"},
        {"id": "API-CHK-002", "item": "OpenAPI/Swagger artifact available", "priority": "P0"},
        {"id": "API-CHK-003", "item": "Negative status code checks included", "priority": "P1"},
    ]
    testcases = [
        {
            "id": f"API-TC-{idx+1:03d}",
            "title": f"Smoke GET {endpoint}",
            "type": "contract-smoke",
            "steps": [
                f"Send GET request to {endpoint}",
                "Verify status code and basic payload structure",
            ],
            "expected": "No 5xx responses and payload shape not empty",
        }
        for idx, endpoint in enumerate(endpoints)
    ]
    known_gaps = ["Payload schema diff checks are not auto-generated in v1.3."]
    assumptions = [f"Endpoint matrix size: {len(strategy.endpoint_matrix_summary)}"]
    return checklist, testcases, known_gaps, assumptions


def _model_assets(intake: NormalizedIntake, strategy: StrategyPlan) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    checklist = [
        {"id": "MOD-CHK-001", "item": "Labels are available for evaluation", "priority": "P0"},
        {"id": "MOD-CHK-002", "item": "Dataset metadata/sample references exist", "priority": "P0"},
        {"id": "MOD-CHK-003", "item": "Quality threshold is defined", "priority": "P1"},
    ]
    testcases = [
        {
            "id": "MOD-TC-001",
            "title": "Compute metadata quality proxy metrics",
            "type": "offline-eval",
            "steps": ["Count labels", "Count dataset samples", "Compute quality score proxy"],
            "expected": "Metrics available for policy gating",
        },
        {
            "id": "MOD-TC-002",
            "title": "Optional endpoint smoke evaluation",
            "type": "online-smoke",
            "steps": ["Invoke model endpoint if configured", "Validate expected token in response"],
            "expected": "No blocking endpoint errors for configured live checks",
        },
    ]
    known_gaps = ["Task-specific benchmark scoring is not generated automatically."]
    assumptions = [f"Evaluation dimensions: {', '.join(strategy.evaluation_dimensions) or 'default'}"]
    return checklist, testcases, known_gaps, assumptions


def _render_checklist_markdown(project_type: str, checklist: list[dict[str, Any]]) -> str:
    lines = [f"# {project_type.upper()} Checklist", "", "| ID | Item | Priority |", "|---|---|---|"]
    for item in checklist:
        lines.append(f"| {item['id']} | {item['item']} | {item['priority']} |")
    return "\n".join(lines) + "\n"


def _render_testcases_markdown(project_type: str, testcases: list[dict[str, Any]]) -> str:
    lines = [f"# {project_type.upper()} Test Cases", ""]
    for testcase in testcases:
        lines.append(f"## {testcase['id']} - {testcase['title']}")
        lines.append(f"- Type: {testcase['type']}")
        lines.append("- Steps:")
        for step in testcase["steps"]:
            lines.append(f"  - {step}")
        lines.append(f"- Expected: {testcase['expected']}")
        lines.append("")
    return "\n".join(lines)


def _bug_report_template(project_type: str, project_name: str) -> str:
    return f"""# Bug Report Template ({project_type.upper()})

## Metadata
- Project: {project_name}
- Product Type: {project_type}
- Environment:
- Build/Version:

## Summary
- Title:
- Severity: (blocker/critical/high/medium/low)
- Expected:
- Actual:

## Reproduction Steps
1.
2.
3.

## Evidence
- Logs:
- Screenshots:
- Traces:
- Artifacts:

## Impact
- Release Gate Impact:
- Workaround:
"""


def generate_assets(
    intake: NormalizedIntake,
    product_type: str,
    strategy: StrategyPlan,
    config: RuntimeConfig,
) -> GeneratedAssetBundle:
    if product_type == "api":
        checklist, testcases, known_gaps, assumptions = _api_assets(intake, strategy)
    elif product_type == "model":
        checklist, testcases, known_gaps, assumptions = _model_assets(intake, strategy)
    else:
        checklist, testcases, known_gaps, assumptions = _web_assets(intake, strategy)

    checklist_payload = {
        "project_name": intake.name,
        "project_type": product_type,
        "manifest_path": intake.manifest_path,
        "items": checklist,
    }
    testcases_payload = {
        "project_name": intake.name,
        "project_type": product_type,
        "manifest_path": intake.manifest_path,
        "cases": testcases,
    }

    checklist_path = Path(config.paths.latest_checklist_file)
    checklist_md_path = Path(config.paths.latest_checklist_markdown_file)
    testcases_path = Path(config.paths.latest_testcases_file)
    testcases_md_path = Path(config.paths.latest_testcases_markdown_file)
    bug_template_path = Path(config.paths.latest_bug_report_template_file)
    index_path = Path(config.paths.latest_generated_assets_index_file)

    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    checklist_md_path.parent.mkdir(parents=True, exist_ok=True)
    testcases_path.parent.mkdir(parents=True, exist_ok=True)
    testcases_md_path.parent.mkdir(parents=True, exist_ok=True)
    bug_template_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    checklist_path.write_text(json.dumps(checklist_payload, indent=2), encoding="utf-8")
    checklist_md_path.write_text(_render_checklist_markdown(product_type, checklist), encoding="utf-8")
    testcases_path.write_text(json.dumps(testcases_payload, indent=2), encoding="utf-8")
    testcases_md_path.write_text(_render_testcases_markdown(product_type, testcases), encoding="utf-8")
    bug_template_path.write_text(_bug_report_template(product_type, intake.name), encoding="utf-8")

    artifact_paths = [
        str(checklist_path),
        str(checklist_md_path),
        str(testcases_path),
        str(testcases_md_path),
        str(bug_template_path),
    ]

    index_payload = {
        "project_name": intake.name,
        "project_type": product_type,
        "manifest_path": intake.manifest_path,
        "artifact_paths": artifact_paths,
        "known_gaps": known_gaps,
        "assumptions": assumptions,
    }
    index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    artifact_paths.append(str(index_path))

    return GeneratedAssetBundle(
        project_type=product_type,
        checklist=checklist,
        testcases=testcases,
        known_gaps=known_gaps,
        assumptions=assumptions,
        artifact_paths=artifact_paths,
    )
