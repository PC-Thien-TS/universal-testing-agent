from pathlib import Path

from orchestrator.project_registry import create_project, get_project, list_projects, update_project


def test_project_registry_create_list_get_update(tmp_path: Path) -> None:
    registry_file = tmp_path / "projects.json"
    created = create_project(
        registry_file,
        name="Sample RAG",
        product_type="rag_app",
        default_manifest_path="manifests/samples/rag_app_eval.yaml",
        project_id="sample-rag",
        description="demo",
        tags=["rag", "demo"],
        environments={"default": {"type": "local"}},
    )
    assert created.project_id == "sample-rag"

    fetched = get_project(registry_file, "sample-rag")
    assert fetched is not None
    assert fetched.name == "Sample RAG"

    projects = list_projects(registry_file)
    assert len(projects) == 1
    assert projects[0].project_id == "sample-rag"

    updated = update_project(registry_file, "sample-rag", {"active": False, "description": "updated"})
    assert updated.active is False
    assert updated.description == "updated"
