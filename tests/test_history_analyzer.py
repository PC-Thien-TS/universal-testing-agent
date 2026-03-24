from orchestrator.history_analyzer import analyze_history_intelligence
from orchestrator.models import CoverageStats, DefectSummary, HistoryRecord, SummaryStats


def _record(
    run_id: str,
    *,
    status: str,
    passed: int,
    failed: int,
    coverage: float,
    defects: int,
    release_ready: bool,
    gate_status: str = "pass",
    timestamp: str,
) -> HistoryRecord:
    return HistoryRecord(
        run_id=run_id,
        timestamp=timestamp,
        project_name="demo",
        project_type="api",
        adapter="api",
        status=status,
        gate_status=gate_status,
        summary=SummaryStats(total_checks=5, passed=passed, failed=failed, blocked=0, skipped=0),
        coverage=CoverageStats(planned_cases=5, executed_cases=5, execution_rate=1.0, requirement_coverage=coverage),
        defects=DefectSummary(high=defects),
        release_ready=release_ready,
    )


def test_history_analyzer_detects_regression_signal() -> None:
    records = [
        _record(
            "r1",
            status="passed",
            passed=5,
            failed=0,
            coverage=0.9,
            defects=0,
            release_ready=True,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
        _record(
            "r2",
            status="failed",
            passed=2,
            failed=3,
            coverage=0.5,
            defects=3,
            release_ready=False,
            gate_status="fail",
            timestamp="2026-01-02T00:00:00+00:00",
        ),
    ]
    intelligence = analyze_history_intelligence(records)
    assert intelligence.runs_analyzed == 2
    assert intelligence.regression_detected is True
    assert intelligence.trend in {"degrading", "stable", "improving"}


def test_history_analyzer_detects_improvement_signal() -> None:
    records = [
        _record(
            "r1",
            status="failed",
            passed=1,
            failed=4,
            coverage=0.3,
            defects=4,
            release_ready=False,
            gate_status="fail",
            timestamp="2026-01-01T00:00:00+00:00",
        ),
        _record(
            "r2",
            status="passed",
            passed=5,
            failed=0,
            coverage=0.9,
            defects=0,
            release_ready=True,
            gate_status="pass",
            timestamp="2026-01-02T00:00:00+00:00",
        ),
    ]
    intelligence = analyze_history_intelligence(records)
    assert intelligence.improvement_detected is True
    assert intelligence.release_readiness_trend in {"improving", "stable", "degrading"}
