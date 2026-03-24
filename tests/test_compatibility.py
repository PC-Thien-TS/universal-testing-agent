from orchestrator.compatibility import analyze_project_compatibility
from orchestrator.models import ProjectRecord


def test_project_compatibility_analysis_for_rag_project() -> None:
    project = ProjectRecord(
        project_id="sample-rag",
        name="sample-rag",
        product_type="rag_app",
        description="",
        tags=[],
        default_manifest_path="manifests/samples/rag_app_eval.yaml",
        environments={"default": {"type": "local", "base_url": ""}},
        active=True,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    summary = analyze_project_compatibility(project, environment_name="default")
    assert summary.project_id == "sample-rag"
    assert summary.plugin_name in {"rag_app", "web"}
    assert summary.support_level in {"full", "partial", "fallback_only"}
