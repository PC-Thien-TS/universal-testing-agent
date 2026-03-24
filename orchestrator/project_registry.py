from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orchestrator.models import ProjectRecord, ProjectRegistryStore, utc_now_iso


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "project"


def _read_store(path: str | Path) -> ProjectRegistryStore:
    registry_path = Path(path)
    if not registry_path.exists():
        return ProjectRegistryStore()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        return ProjectRegistryStore.model_validate(payload)
    except Exception:
        return ProjectRegistryStore()


def _write_store(path: str | Path, store: ProjectRegistryStore) -> None:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(store.model_dump(mode="json"), indent=2), encoding="utf-8")


def _find_project(store: ProjectRegistryStore, project_id: str) -> ProjectRecord | None:
    for project in store.projects:
        if project.project_id == project_id:
            return project
    return None


def create_project(
    registry_path: str | Path,
    *,
    name: str,
    product_type: str,
    default_manifest_path: str,
    project_id: str | None = None,
    description: str = "",
    tags: list[str] | None = None,
    environments: dict[str, dict[str, Any]] | None = None,
    active: bool = True,
) -> ProjectRecord:
    store = _read_store(registry_path)
    resolved_project_id = (project_id or _slugify(name)).strip()
    if _find_project(store, resolved_project_id):
        raise ValueError(f"Project '{resolved_project_id}' already exists.")

    now = utc_now_iso()
    record = ProjectRecord(
        project_id=resolved_project_id,
        name=name,
        product_type=product_type,
        description=description,
        tags=tags or [],
        default_manifest_path=default_manifest_path,
        environments=environments or {},
        active=active,
        created_at=now,
        updated_at=now,
    )
    store.projects.append(record)
    store.projects = sorted(store.projects, key=lambda item: item.project_id)
    _write_store(registry_path, store)
    return record


def update_project(
    registry_path: str | Path,
    project_id: str,
    updates: dict[str, Any],
) -> ProjectRecord:
    store = _read_store(registry_path)
    current = _find_project(store, project_id)
    if current is None:
        raise ValueError(f"Project '{project_id}' not found.")

    payload = current.model_dump(mode="json")
    payload.update({key: value for key, value in updates.items() if value is not None})
    payload["project_id"] = project_id
    payload["updated_at"] = utc_now_iso()
    updated = ProjectRecord.model_validate(payload)

    store.projects = [item if item.project_id != project_id else updated for item in store.projects]
    store.projects = sorted(store.projects, key=lambda item: item.project_id)
    _write_store(registry_path, store)
    return updated


def get_project(registry_path: str | Path, project_id: str) -> ProjectRecord | None:
    store = _read_store(registry_path)
    return _find_project(store, project_id)


def list_projects(registry_path: str | Path, *, active_only: bool = False) -> list[ProjectRecord]:
    store = _read_store(registry_path)
    projects = list(store.projects)
    if active_only:
        projects = [item for item in projects if item.active]
    return sorted(projects, key=lambda item: item.project_id)

