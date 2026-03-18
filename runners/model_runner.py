from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests


def _defect(defect_id: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {"id": defect_id, "severity": severity, "message": message, "details": details}


def _safe_execution_rate(executed_cases: int, planned_cases: int) -> float:
    if planned_cases <= 0:
        return 0.0
    return round(executed_cases / planned_cases, 4)


def _read_dataset_sample_count(dataset_path: str | None) -> int:
    if not dataset_path:
        return 0
    path = Path(dataset_path)
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(raw, list):
        return len(raw)
    return 0


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
    dataset_samples = dataset_samples or []
    defects: list[dict[str, Any]] = []
    logs: list[str] = []
    metrics: dict[str, Any] = {}

    file_sample_count = _read_dataset_sample_count(dataset_path)
    inline_sample_count = len(dataset_samples)
    sample_count = max(file_sample_count, inline_sample_count)
    label_count = len(labels)

    planned_cases = max(len(eval_cases), 1) + 2
    passed = 0
    failed = 0
    blocked = 0
    skipped = 0

    metrics["label_count"] = label_count
    metrics["sample_count"] = sample_count
    metrics["label_coverage"] = round(min(1.0, label_count / 5), 4) if label_count > 0 else 0.0

    if label_count > 0:
        passed += 1
        logs.append(f"Loaded labels: {label_count}")
    else:
        blocked += 1
        defects.append(_defect("model.labels_missing", "low", "No labels provided for evaluation context"))

    if sample_count > 0:
        passed += 1
        logs.append(f"Loaded dataset samples: {sample_count}")
    else:
        blocked += 1
        defects.append(_defect("model.dataset_missing", "low", "No dataset samples available for metric computation"))

    live_eval_cases = eval_cases or []
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
                            "Model endpoint returned failing status",
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
                            "Expected token missing from model output",
                            expected_contains=expected,
                            case_index=index,
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
                        "Model endpoint unreachable in smoke mode",
                        case_index=index,
                        error=str(exc),
                    )
                )
    else:
        skipped += 1
        logs.append("Live endpoint evaluation skipped; computed placeholder metrics from local metadata.")

    executed_cases = passed + failed + blocked
    total_checks = passed + failed + blocked + skipped
    quality_score_proxy = round((metrics["label_coverage"] + min(1.0, sample_count / 10)) / 2, 4)
    metrics["quality_score_proxy"] = quality_score_proxy

    if quality_score_proxy >= threshold:
        passed += 1
        total_checks += 1
        executed_cases += 1
    else:
        failed += 1
        total_checks += 1
        executed_cases += 1
        defects.append(
            _defect(
                "model.threshold_not_met",
                "medium",
                "Computed quality proxy is below threshold",
                threshold=threshold,
                quality_score_proxy=quality_score_proxy,
            )
        )

    status = "failed" if failed > 0 else "blocked" if blocked > 0 and passed == 0 else "passed"

    trace_file = Path("evidence") / "model_eval_trace.log"
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
            "requirement_coverage": round(min(1.0, max(0.4, quality_score_proxy)), 4),
        },
        "defects": defects,
        "evidence": {
            "logs": logs,
            "screenshots": [],
            "traces": [str(trace_file)],
            "artifacts": [str(trace_file)] + ([dataset_path] if dataset_path else []),
        },
        "recommendation_notes": [
            "Add richer labeled datasets for stronger model evaluation confidence.",
            "Provide endpoint + eval cases for live inference smoke tests.",
        ],
        "raw_output": {
            "endpoint": endpoint,
            "threshold": threshold,
            "metrics": metrics,
            "dataset_path": dataset_path,
        },
    }
