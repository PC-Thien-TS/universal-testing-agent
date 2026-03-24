from pathlib import Path

from orchestrator.dataset_loader import (
    compute_classification_metrics,
    evaluate_llm_dataset,
    evaluate_rag_dataset,
    load_json_dataset,
    resolve_dataset_path,
)


def test_load_json_dataset_reads_valid_file() -> None:
    dataset_path = Path("manifests/samples/model_basalt_dataset.json")
    rows = load_json_dataset(str(dataset_path))
    assert rows
    assert isinstance(rows[0], dict)


def test_resolve_dataset_path_prefers_request_then_artifacts() -> None:
    from_request = resolve_dataset_path({"dataset_path": "manifests/samples/llm_eval_dataset.json"}, [])
    assert from_request == "manifests/samples/llm_eval_dataset.json"

    from_artifacts = resolve_dataset_path(
        {},
        [{"name": "baseline", "type": "dataset", "path": "manifests/samples/llm_eval_dataset.json"}],
    )
    assert from_artifacts == "manifests/samples/llm_eval_dataset.json"


def test_compute_classification_metrics_outputs_expected_keys() -> None:
    metrics = compute_classification_metrics(
        samples=[
            {"expected_label": "safe", "predicted": "safe"},
            {"expected_label": "unsafe", "predicted": "unsafe"},
            {"expected_label": "unsafe", "predicted": "safe"},
        ],
        labels=["safe", "unsafe"],
    )
    assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1_score"}
    assert 0.0 <= metrics["accuracy"] <= 1.0


def test_rag_and_llm_dataset_evaluators_are_deterministic() -> None:
    rag = evaluate_rag_dataset(load_json_dataset("manifests/samples/rag_eval_dataset.json"))
    llm = evaluate_llm_dataset(load_json_dataset("manifests/samples/llm_eval_dataset.json"))
    assert set(rag.keys()) == {"correctness_rate", "grounding_rate", "hallucination_rate"}
    assert set(llm.keys()) == {"consistency_rate", "expected_output_rate"}
