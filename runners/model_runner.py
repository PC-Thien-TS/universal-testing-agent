from __future__ import annotations

import json
from typing import Any

import requests


def _defect(defect_id: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "id": defect_id,
        "severity": severity,
        "message": message,
        "details": details,
    }


def _extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("output", "text", "response", "message", "content"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(payload)
    return str(payload)


def run_model_evaluation(endpoint: str, eval_cases: list[dict[str, Any]], timeout_s: int, threshold: float) -> dict[str, Any]:
    if not endpoint:
        return {
            "status": "failed",
            "passed": 0,
            "failed": 1,
            "defects": [_defect("model.missing_endpoint", "high", "No model endpoint provided")],
            "raw_output": {},
        }

    cases = eval_cases or [{"prompt": "Ping", "expected_contains": "pong"}]
    defects: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    details: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        prompt = str(case.get("prompt", ""))
        expected = case.get("expected_contains")
        payload = case.get("payload") or {"prompt": prompt}
        method = str(case.get("method", "POST")).upper()

        try:
            response = requests.request(method, endpoint, json=payload, timeout=timeout_s)
            try:
                body: Any = response.json()
            except Exception:
                body = response.text
            output_text = _extract_text(body)

            case_record = {
                "case_index": index,
                "status_code": response.status_code,
                "expected_contains": expected,
                "output_excerpt": output_text[:200],
            }

            if response.status_code >= 400:
                failed += 1
                defects.append(
                    _defect(
                        "model.http_error",
                        "high",
                        "Model endpoint returned failing status",
                        case_index=index,
                        status_code=response.status_code,
                    )
                )
            elif expected and expected not in output_text:
                failed += 1
                defects.append(
                    _defect(
                        "model.assertion_failed",
                        "medium",
                        "Expected token missing from model output",
                        case_index=index,
                        expected_contains=expected,
                    )
                )
            else:
                passed += 1

            details.append(case_record)

        except Exception as exc:
            failed += 1
            defects.append(
                _defect(
                    "model.request_failed",
                    "critical",
                    "Model request failed",
                    case_index=index,
                    error=str(exc),
                )
            )

    total = max(len(cases), 1)
    score = passed / total

    if score < threshold:
        defects.append(
            _defect(
                "model.quality_threshold",
                "high",
                "Model quality score is below threshold",
                score=score,
                threshold=threshold,
            )
        )

    status = "passed" if failed == 0 and score >= threshold else "failed"
    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "defects": defects,
        "raw_output": {
            "endpoint": endpoint,
            "threshold": threshold,
            "score": round(score, 4),
            "cases": details,
        },
    }
