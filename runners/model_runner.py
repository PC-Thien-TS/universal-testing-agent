from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from orchestrator.dataset_loader import compute_classification_metrics, load_json_dataset


def _defect(
    defect_id: str,
    severity: str,
    message: str,
    *,
    category: str = "model",
    reproducibility: str = "deterministic",
    confidence_score: float = 0.95,
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


def run_model_evaluation(
    endpoint: str,
    eval_cases: list[dict[str, Any]],
    timeout_s: int,
    threshold: float,
    labels: list[str] | None = None,
    dataset_path: str | None = None,
    dataset_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    labels = labels or []
    inline_samples = [item for item in (dataset_samples or []) if isinstance(item, dict)]
    file_samples = load_json_dataset(dataset_path)
    samples = file_samples or inline_samples

    defects: list[dict[str, Any]] = []
    logs: list[str] = []
    metrics: dict[str, Any] = {}

    planned_cases = max(len(eval_cases), 1) + 4
    passed = 0
    failed = 0
    blocked = 0
    skipped = 0

    if samples:
        passed += 1
        logs.append(f"Loaded dataset samples: {len(samples)}")
    else:
        blocked += 1
        defects.append(
            _defect(
                "model.dataset_missing",
                "medium",
                "No dataset samples available for metric computation.",
                category="data",
                confidence_score=0.9,
            )
        )

    metrics.update(compute_classification_metrics(samples, labels))
    metrics["sample_count"] = len(samples)
    metrics["label_count"] = len(labels)
    if metrics["sample_count"] > 0:
        passed += 1
    else:
        blocked += 1

    live_eval_cases = [item for item in (eval_cases or []) if isinstance(item, dict)]
    if endpoint and live_eval_cases:
        for index, case in enumerate(live_eval_cases, start=1):
            payload = case.get("payload") or {"prompt": case.get("prompt", "")}
            method = str(case.get("method", "POST")).upper()
            expected = str(case.get("expected_contains", "")).strip()
            try:
                response = requests.request(method, endpoint, json=payload, timeout=max(timeout_s, 1))
                body_text = response.text
                logs.append(f"{method} {endpoint} -> {response.status_code}")
                if response.status_code >= 400:
                    failed += 1
                    defects.append(
                        _defect(
                            "model.http_error",
                            "high",
                            "Model endpoint returned failing status.",
                            status_code=response.status_code,
                            case_index=index,
                        )
                    )
                elif expected and expected not in body_text:
                    failed += 1
                    defects.append(
                        _defect(
                            "model.assertion_failed",
                            "medium",
                            "Expected token missing from model output.",
                            case_index=index,
                            expected_contains=expected,
                        )
                    )
                else:
                    passed += 1
            except Exception as exc:
                blocked += 1
                defects.append(
                    _defect(
                        "model.endpoint_unavailable",
                        "low",
                        "Model endpoint unreachable in smoke mode.",
                        category="performance",
                        reproducibility="unknown",
                        confidence_score=0.7,
                        case_index=index,
                        error=str(exc),
                    )
                )
    else:
        skipped += 1
        logs.append("Live endpoint evaluation skipped; using offline metrics.")

    if metrics["accuracy"] >= threshold:
        passed += 1
        logs.append(f"Accuracy gate passed: {metrics['accuracy']} >= {threshold}")
    else:
        failed += 1
        defects.append(
            _defect(
                "model.accuracy_threshold_not_met",
                "high",
                "Accuracy is below acceptance threshold.",
                threshold=threshold,
                accuracy=metrics["accuracy"],
            )
        )

    if metrics["f1_score"] >= threshold:
        passed += 1
        logs.append(f"F1 gate passed: {metrics['f1_score']} >= {threshold}")
    else:
        failed += 1
        defects.append(
            _defect(
                "model.f1_threshold_not_met",
                "medium",
                "F1 score is below acceptance threshold.",
                threshold=threshold,
                f1_score=metrics["f1_score"],
            )
        )

    executed_cases = passed + failed + blocked
    total_checks = passed + failed + blocked + skipped
    quality_proxy = (metrics["accuracy"] + metrics["precision"] + metrics["recall"] + metrics["f1_score"]) / 4
    status = "failed" if failed > 0 else "blocked" if blocked > 0 and passed == 0 else "passed"

    trace_file = Path("evidence") / "model_eval_trace.log"
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    trace_file.write_text("\n".join(logs), encoding="utf-8")

    artifacts = [str(trace_file)]
    if dataset_path:
        artifacts.append(dataset_path)

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
            "requirement_coverage": round(min(1.0, max(0.35, quality_proxy)), 4),
        },
        "defects": defects,
        "evidence": {
            "logs": logs,
            "screenshots": [],
            "traces": [str(trace_file)],
            "artifacts": artifacts,
        },
        "recommendation_notes": [
            "Model evaluation computes accuracy, precision, recall, and F1 from dataset-driven samples.",
            "Provide larger labeled datasets to stabilize metric confidence.",
        ],
        "raw_output": {
            "endpoint": endpoint,
            "threshold": threshold,
            "metrics": metrics,
            "dataset_path": dataset_path,
            "dataset_evaluation_summary": {
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1_score": metrics["f1_score"],
                "sample_count": metrics["sample_count"],
            },
        },
    }
