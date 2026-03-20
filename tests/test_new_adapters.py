from orchestrator.config import load_runtime_config
from orchestrator.executor import execute_pipeline
from orchestrator.models import Artifact, NormalizedIntake
from orchestrator.planner import generate_test_strategy
from orchestrator.router import select_adapter


def test_mobile_adapter_execution_is_offline_safe() -> None:
    config = load_runtime_config()
    intake = NormalizedIntake(
        manifest_path="manifests/samples/mobile_app_smoke.yaml",
        name="mobile-app-smoke",
        project_type="mobile",
        artifacts=[Artifact(name="meta", type="mobile", path="manifests/samples/mobile_bundle_metadata.json")],
        request={"app_id": "com.example.travel", "permissions": ["camera"]},
        entry_points=[{"name": "home", "route": "home"}],
        acceptance={},
        outputs={},
        auth={"required": True},
        constraints=[],
        api={},
        model={},
    )
    strategy = generate_test_strategy(intake, "mobile")
    adapter = select_adapter("mobile", config)
    envelope = execute_pipeline(intake, "mobile", strategy, adapter)
    assert envelope.adapter == "mobile"
    assert envelope.summary.total_checks >= 1


def test_llm_app_adapter_execution_is_offline_safe() -> None:
    config = load_runtime_config()
    intake = NormalizedIntake(
        manifest_path="manifests/samples/llm_app_eval.yaml",
        name="llm-app-eval",
        project_type="llm_app",
        labels=["safe"],
        artifacts=[Artifact(name="dataset", type="dataset", path="manifests/samples/llm_app_eval_dataset.json")],
        request={
            "tools": ["search"],
            "fallback_strategy": "safe-default",
            "eval_cases": [{"prompt": "hello", "expected_contains": "hello", "mock_response": "hello safe"}],
        },
        acceptance={},
        outputs={},
        auth={},
        constraints=[],
        api={},
        model={},
    )
    strategy = generate_test_strategy(intake, "llm_app")
    adapter = select_adapter("llm_app", config)
    envelope = execute_pipeline(intake, "llm_app", strategy, adapter)
    assert envelope.adapter == "llm_app"
    assert envelope.summary.total_checks >= 1
