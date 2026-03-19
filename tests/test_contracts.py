from pathlib import Path

from orchestrator.contracts import validate_contracts


def test_validate_contracts_for_api_manifest() -> None:
    result = validate_contracts(Path("manifests/samples/api_verify_store.yaml"))
    assert result.verdict in {"pass", "fail"}
    assert "result_contract_basics" in result.checks


def test_validate_contracts_for_model_manifest() -> None:
    result = validate_contracts(Path("manifests/samples/model_basalt.yaml"))
    assert "model_contract_basics" in result.checks
