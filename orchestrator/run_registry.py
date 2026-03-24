from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import RunRegistryRecord, RunRegistryStore


def _read_store(path: str | Path) -> RunRegistryStore:
    registry_path = Path(path)
    if not registry_path.exists():
        return RunRegistryStore()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        return RunRegistryStore.model_validate(payload)
    except Exception:
        return RunRegistryStore()


def _write_store(path: str | Path, store: RunRegistryStore) -> None:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(store.model_dump(mode="json"), indent=2), encoding="utf-8")


def add_run_record(path: str | Path, record: RunRegistryRecord) -> RunRegistryRecord:
    store = _read_store(path)
    store.runs = [item for item in store.runs if not (item.run_id == record.run_id and item.project_id == record.project_id)]
    store.runs.append(record)
    store.runs = sorted(store.runs, key=lambda item: item.started_at)
    _write_store(path, store)
    return record


def list_runs(path: str | Path, project_id: str, *, limit: int | None = None) -> list[RunRegistryRecord]:
    store = _read_store(path)
    records = [item for item in store.runs if item.project_id == project_id]
    records = sorted(records, key=lambda item: item.started_at, reverse=True)
    if limit is not None and limit > 0:
        return records[:limit]
    return records


def latest_run(path: str | Path, project_id: str) -> RunRegistryRecord | None:
    records = list_runs(path, project_id, limit=1)
    if not records:
        return None
    return records[0]


def summarize_run_history(path: str | Path, project_id: str) -> dict[str, object]:
    records = list_runs(path, project_id)
    if not records:
        return {
            "project_id": project_id,
            "total_runs": 0,
            "pass_rate": 0.0,
            "gate_pass_rate": 0.0,
            "latest_status": None,
            "latest_gate_status": None,
        }

    passed_runs = sum(1 for item in records if item.status == "passed")
    gate_pass_runs = sum(1 for item in records if item.gate_status == "pass")
    return {
        "project_id": project_id,
        "total_runs": len(records),
        "pass_rate": round(passed_runs / len(records), 4),
        "gate_pass_rate": round(gate_pass_runs / len(records), 4),
        "latest_status": records[0].status,
        "latest_gate_status": records[0].gate_status,
    }

