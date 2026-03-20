from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _defect(defect_id: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {"id": defect_id, "severity": severity, "message": message, "details": details}


def _safe_execution_rate(executed_cases: int, planned_cases: int) -> float:
    if planned_cases <= 0:
        return 0.0
    return round(executed_cases / planned_cases, 4)


def _load_json_list(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    candidate = Path(path)
    if not candidate.exists():
        return []
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def run_rag_app_smoke(
    eval_cases: list[dict[str, Any]],
    corpus_path: str | None,
    require_citations: bool,
    tool_names: list[str],
    fallback_strategy: str,
    evidence_dir: str,
) -> dict[str, Any]:
    logs: list[str] = []
    defects: list[dict[str, Any]] = []
    corpus_items = _load_json_list(corpus_path)

    planned_cases = max(len(eval_cases), 1) + 4
    passed = 0
    failed = 0
    blocked = 0
    skipped = 0

    if corpus_items:
        passed += 1
        logs.append(f"Corpus loaded with {len(corpus_items)} records.")
    else:
        blocked += 1
        defects.append(_defect("rag.corpus_missing", "medium", "No retrieval corpus data available."))

    if tool_names:
        passed += 1
        logs.append(f"Retrieval tools configured: {', '.join(tool_names)}")
    else:
        blocked += 1
        defects.append(_defect("rag.tools_missing", "low", "No retrieval tool configured for rag_app."))

    if fallback_strategy:
        passed += 1
        logs.append(f"Fallback strategy configured: {fallback_strategy}")
    else:
        blocked += 1
        defects.append(_defect("rag.fallback_missing", "medium", "No fallback strategy configured for rag_app."))

    for index, case in enumerate(eval_cases or [{"prompt": "health check", "expected_contains": "answer"}], start=1):
        expected = str(case.get("expected_contains", "")).strip().lower()
        response = str(case.get("mock_response", case.get("prompt", ""))).lower()
        citation = str(case.get("expected_citation", "")).strip().lower()
        context_hit = bool(case.get("context_hit", True))

        if not context_hit:
            failed += 1
            defects.append(_defect("rag.context_miss", "high", "Retrieval context grounding signal is missing.", case_index=index))
            continue

        if expected and expected not in response:
            failed += 1
            defects.append(
                _defect(
                    "rag.expected_missing",
                    "medium",
                    "Expected token not found in rag_app response.",
                    case_index=index,
                    expected_contains=expected,
                )
            )
            continue

        if require_citations and citation and citation not in response:
            failed += 1
            defects.append(
                _defect(
                    "rag.citation_missing",
                    "high",
                    "Citation requirement not satisfied in response.",
                    case_index=index,
                    expected_citation=citation,
                )
            )
            continue

        passed += 1
        logs.append(f"Case {index} passed retrieval quality checks.")

    total_checks = passed + failed + blocked + skipped
    executed_cases = passed + failed + blocked
    status = "failed" if failed > 0 else "blocked" if blocked > 0 and passed == 0 else "passed"
    requirement_coverage = round(min(1.0, max(0.4, passed / max(planned_cases, 1))), 4)

    trace_file = Path(evidence_dir) / "rag_app_smoke_trace.log"
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
            "artifacts": [str(trace_file)] + ([corpus_path] if corpus_path else []),
        },
        "recommendation_notes": [
            "rag_app runner executed offline-safe retrieval smoke checks; add live retrieval validation for production confidence."
        ],
        "raw_output": {
            "corpus_path": corpus_path,
            "require_citations": require_citations,
            "tool_names": tool_names,
            "fallback_strategy": fallback_strategy,
        },
    }
