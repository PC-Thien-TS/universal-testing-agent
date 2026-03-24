from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from orchestrator.models import HistoryIntelligence, HistoryRecord


def _direction(first: float, last: float) -> str:
    delta = last - first
    if delta > 0.02:
        return "improving"
    if delta < -0.02:
        return "degrading"
    return "stable"


def _release_readiness_trend(ordered: list[HistoryRecord]) -> str:
    if not ordered:
        return "stable"
    midpoint = max(len(ordered) // 2, 1)
    first_half = ordered[:midpoint]
    second_half = ordered[midpoint:]
    first_rate = sum(1 for item in first_half if item.release_ready) / max(len(first_half), 1)
    second_rate = sum(1 for item in second_half if item.release_ready) / max(len(second_half), 1)
    return _direction(first_rate, second_rate)


def _flaky_classification(ordered: list[HistoryRecord]) -> tuple[str, float, bool]:
    if not ordered:
        return "stable", 1.0, False
    recent = ordered[-8:]
    statuses = [item.status for item in recent]
    switches = sum(1 for index in range(1, len(statuses)) if statuses[index] != statuses[index - 1])
    gate_statuses = [item.gate_status for item in recent if item.gate_status]
    gate_switches = sum(1 for index in range(1, len(gate_statuses)) if gate_statuses[index] != gate_statuses[index - 1])
    gate_instability = gate_switches >= 2

    has_failures = any(status in {"failed", "error", "blocked"} for status in statuses)
    has_passes = any(status == "passed" for status in statuses)
    if switches >= 3 and has_failures and has_passes:
        flaky = "flaky"
    elif switches >= 1:
        flaky = "unstable"
    else:
        flaky = "stable"

    stability_score = max(0.0, round(1.0 - (switches / max(len(statuses) - 1, 1)), 4))
    return flaky, stability_score, gate_instability


def analyze_history_intelligence(records: list[HistoryRecord]) -> HistoryIntelligence:
    if not records:
        return HistoryIntelligence(runs_analyzed=0)

    ordered = sorted(records, key=lambda item: item.timestamp)
    recent = ordered[-10:]
    pass_rates = [item.summary.passed / max(item.summary.total_checks, 1) for item in recent]
    defect_counts = [
        item.defects.blocker + item.defects.critical + item.defects.high + item.defects.medium + item.defects.low
        for item in recent
    ]

    trend = _direction(pass_rates[0], pass_rates[-1])
    release_trend = _release_readiness_trend(recent)
    flaky_classification, stability_score, gate_instability = _flaky_classification(recent)

    regression_detected = False
    improvement_detected = False
    if len(recent) >= 2:
        last = recent[-1]
        previous = recent[-2]
        regression_detected = (
            (last.status in {"failed", "error"} and previous.status == "passed")
            or (defect_counts[-1] > defect_counts[-2] + 1)
            or (not last.release_ready and previous.release_ready)
        )
        improvement_detected = (
            (last.status == "passed" and previous.status in {"failed", "error", "blocked"})
            or (defect_counts[-1] + 1 < defect_counts[-2])
            or (last.release_ready and not previous.release_ready)
        )

    failing_counter: Counter[str] = Counter()
    for item in recent:
        if item.status in {"failed", "error", "blocked"}:
            key = f"{item.project_type}:{item.adapter}"
            failing_counter[key] += 1
    failing_areas = [name for name, _count in failing_counter.most_common(5)]

    return HistoryIntelligence(
        runs_analyzed=len(recent),
        regression_detected=regression_detected,
        improvement_detected=improvement_detected,
        trend=trend,
        stability_score=stability_score,
        failing_areas=failing_areas,
        release_readiness_trend=release_trend,
        flaky_classification=flaky_classification,
        gate_instability=gate_instability,
    )


def render_history_intelligence_markdown(intelligence: HistoryIntelligence) -> str:
    return f"""# History Intelligence

- Runs analyzed: `{intelligence.runs_analyzed}`
- Trend: `{intelligence.trend}`
- Regression detected: `{intelligence.regression_detected}`
- Improvement detected: `{intelligence.improvement_detected}`
- Stability score: `{intelligence.stability_score}`
- Flaky classification: `{intelligence.flaky_classification}`
- Gate instability: `{intelligence.gate_instability}`
- Release readiness trend: `{intelligence.release_readiness_trend}`
- Failing areas: {", ".join(intelligence.failing_areas) if intelligence.failing_areas else "(none)"}
"""


def save_history_intelligence(
    intelligence: HistoryIntelligence,
    output_json: str | Path,
    output_md: str | Path,
) -> tuple[Path, Path]:
    json_path = Path(output_json)
    md_path = Path(output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(intelligence.model_dump(mode="json"), indent=2), encoding="utf-8")
    md_path.write_text(render_history_intelligence_markdown(intelligence), encoding="utf-8")
    return json_path, md_path
