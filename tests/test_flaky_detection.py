from orchestrator.history_analyzer import analyze_history_intelligence
from orchestrator.models import CoverageStats, DefectSummary, HistoryRecord, SummaryStats


def _record(run_id: str, status: str, gate_status: str, ts: str) -> HistoryRecord:
    failed = 1 if status == "failed" else 0
    passed = 1 if status == "passed" else 0
    return HistoryRecord(
        run_id=run_id,
        timestamp=ts,
        project_name="demo",
        project_type="llm_app",
        adapter="llm_app",
        status=status,
        gate_status=gate_status,
        summary=SummaryStats(total_checks=1, passed=passed, failed=failed, blocked=0, skipped=0),
        coverage=CoverageStats(planned_cases=1, executed_cases=1, execution_rate=1.0, requirement_coverage=0.8),
        defects=DefectSummary(high=failed),
        release_ready=status == "passed",
    )


def test_flaky_classification_for_switching_statuses() -> None:
    records = [
        _record("r1", "passed", "pass", "2026-01-01T00:00:00+00:00"),
        _record("r2", "failed", "fail", "2026-01-02T00:00:00+00:00"),
        _record("r3", "passed", "pass", "2026-01-03T00:00:00+00:00"),
        _record("r4", "failed", "fail", "2026-01-04T00:00:00+00:00"),
        _record("r5", "passed", "pass", "2026-01-05T00:00:00+00:00"),
    ]
    intelligence = analyze_history_intelligence(records)
    assert intelligence.flaky_classification in {"flaky", "unstable"}
    assert 0.0 <= intelligence.stability_score <= 1.0


def test_flaky_classification_stable_for_consistent_runs() -> None:
    records = [
        _record("r1", "passed", "pass", "2026-01-01T00:00:00+00:00"),
        _record("r2", "passed", "pass", "2026-01-02T00:00:00+00:00"),
        _record("r3", "passed", "pass", "2026-01-03T00:00:00+00:00"),
        _record("r4", "passed", "pass", "2026-01-04T00:00:00+00:00"),
    ]
    intelligence = analyze_history_intelligence(records)
    assert intelligence.flaky_classification == "stable"
    assert intelligence.gate_instability is False
