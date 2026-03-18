from orchestrator.classifier import classify_product
from orchestrator.models import Artifact, NormalizedIntake


def _intake(
    *,
    url: str | None = None,
    artifacts: list[Artifact] | None = None,
    project_type: str = "auto",
    model: dict | None = None,
) -> NormalizedIntake:
    return NormalizedIntake(
        manifest_path="test.yaml",
        name="test",
        project_type=project_type,
        url=url,
        target=url,
        artifacts=artifacts or [],
        environment={},
        request={},
        acceptance={},
        outputs={},
        auth={},
        constraints=[],
        api={},
        model=model or {},
    )


def test_classifier_detects_web_from_url() -> None:
    intake = _intake(url="https://example.com")
    assert classify_product(intake) == "web"


def test_classifier_detects_api_from_openapi_artifact() -> None:
    intake = _intake(artifacts=[Artifact(name="openapi", type="spec", path="openapi.json")])
    assert classify_product(intake) == "api"


def test_classifier_detects_model_from_endpoint() -> None:
    intake = _intake(model={"endpoint": "https://api.example.com/v1/model"})
    assert classify_product(intake) == "model"
