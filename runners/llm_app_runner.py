from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.dataset_loader import evaluate_llm_dataset, load_json_dataset


def _defect(
    defect_id: str,
    severity: str,
    message: str,
    *,
    category: str = "model",
    reproducibility: str = "deterministic",
    confidence_score: float = 0.9,
    **details: Any,
) -> dict[str, Any]:
    return {
        "id": defect_id,
        "severity": severity,
        "category": category,
        "reproducibility": reproducibility,
        "confidence_score": confidence_score,
        "message": message,
        "details": details,
    }


def _safe_execution_rate(executed_cases: int, planned_cases: int) -> float:
    if planned_cases <= 0:
        return 0.0
    return round(executed_cases / planned_cases, 4)


def run_llm_app_smoke(
    eval_cases: list[dict[str, Any]],
    labels: list[str],
    dataset_path: str | None,
    tool_names: list[str],
    fallback_strategy: str,
    evidence_dir: str,
) -> dict[str, Any]:
    logs: list[str] = []
    defects: list[dict[str, Any]] = []
    dataset_samples = load_json_dataset(dataset_path)

    planned_cases = max(len(eval_cases), 1) + 5
    passed = 0
    failed = 0
    blocked = 0
    skipped = 0

    if labels:
        passed += 1
        logs.append(f"Label taxonomy loaded: {len(labels)}")
    else:
        blocked += 1
        defects.append(
            _defect(
                "llm.labels_missing",
                "low",
                "No label taxonomy configured for llm_app evaluation.",
                category="data",
            )
        )

    if dataset_samples:
        passed += 1
        logs.append(f"Dataset samples loaded: {len(dataset_samples)}")
    else:
        blocked += 1
        defects.append(
            _defect(
                "llm.dataset_missing",
                "low",
                "No llm_app dataset samples available.",
                category="data",
            )
        )

    if tool_names:
        passed += 1
        logs.append(f"Tool readiness checks prepared: {', '.join(tool_names)}")
    else:
        blocked += 1
        defects.append(
            _defect(
                "llm.tools_missing",
                "low",
                "No tools declared for tool-use readiness checks.",
                category="functional",
            )
        )

    if fallback_strategy:
        passed += 1
        logs.append(f"Fallback strategy configured: {fallback_strategy}")
    else:
        blocked += 1
        defects.append(
            _defect(
                "llm.fallback_missing",
                "medium",
                "No fallback strategy configured.",
                category="functional",
            )
        )

    cases = eval_cases or [{"prompt": "health check", "expected_contains": "ok"}]
    for index, case in enumerate(cases, start=1):
        prompt = str(case.get("prompt", ""))
        expected = str(case.get("expected_contains", case.get("expected_output", ""))).lower().strip()
        candidate = str(case.get("mock_response", case.get("response", prompt))).lower()
        if expected and expected in candidate:
            passed += 1
            logs.append(f"Case {index}: expected token detected.")
        elif expected:
            failed += 1
            defects.append(
                _defect(
                    "llm.expected_token_missing",
                    "medium",
                    "Expected token not present in simulated response.",
                    case_index=index,
                    expected_contains=expected,
                )
            )
        else:
            skipped += 1
            logs.append(f"Case {index}: no explicit expected token; skipped strict assertion.")

    dataset_summary = evaluate_llm_dataset(dataset_samples or cases)
    if dataset_summary["expected_output_rate"] < 0.5 and (dataset_samples or cases):
        failed += 1
        defects.append(
            _defect(
                "llm.dataset_expected_output_low",
                "medium",
                "Dataset expected output match rate is below 0.5.",
                expected_output_rate=dataset_summary["expected_output_rate"],
            )
        )
    else:
        passed += 1

    total_checks = passed + failed + blocked + skipped
    executed_cases = passed + failed + blocked
    status = "failed" if failed > 0 else "blocked" if blocked > 0 and passed == 0 else "passed"
    requirement_coverage = round(min(1.0, max(0.4, passed / max(planned_cases, 1))), 4)

    trace_file = Path(evidence_dir) / "llm_app_smoke_trace.log"
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    trace_file.write_text("\n".join(logs), encoding="utf-8")

    return {
        "status": status,
        "summary": {
            "total_checks": total_checks,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
        },
        "coverage": {
            "planned_cases": planned_cases,
            "executed_cases": executed_cases,
            "execution_rate": _safe_execution_rate(executed_cases, planned_cases),
            "requirement_coverage": requirement_coverage,
        },
        "defects": defects,
        "evidence": {
            "logs": logs,
            "screenshots": [],
            "traces": [str(trace_file)],
            "artifacts": [str(trace_file)] + ([dataset_path] if dataset_path else []),
        },
        "recommendation_notes": [
            "llm_app checks include expected-token assertions and dataset consistency heuristics.",
            "Add live evaluator judgments for deeper conversational quality confidence.",
        ],
        "raw_output": {
            "skeleton_mode": True,
            "tool_names": tool_names,
            "fallback_strategy": fallback_strategy,
            "dataset_path": dataset_path,
            "dataset_evaluation_summary": dataset_summary,
        },
    }
