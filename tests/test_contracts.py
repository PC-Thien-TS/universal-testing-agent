from pathlib import Path

from orchestrator.contracts import validate_contracts


def test_validate_contracts_for_api_manifest() -> None:
    result = validate_contracts(Path("manifests/samples/api_verify_store.yaml"))
    assert result.verdict in {"pass", "fail"}
    assert "result_contract_basics" in result.checks


def test_validate_contracts_for_model_manifest() -> None:
    result = validate_contracts(Path("manifests/samples/model_basalt.yaml"))
    assert "model_contract_basics" in result.checks


def test_validate_contracts_for_mobile_and_llm_app_manifests() -> None:
    mobile_result = validate_contracts(Path("manifests/samples/mobile_app_smoke.yaml"))
    llm_result = validate_contracts(Path("manifests/samples/llm_app_eval.yaml"))
    assert "mobile_contract_basics" in mobile_result.checks
    assert "llm_app_contract_basics" in llm_result.checks
