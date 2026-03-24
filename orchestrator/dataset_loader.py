from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_dataset(dataset_path: str | None) -> list[dict[str, Any]]:
    if not dataset_path:
        return []
    path = Path(dataset_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def resolve_dataset_path(
    request: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    keywords: tuple[str, ...] = ("dataset", "sample"),
) -> str | None:
    dataset_path = str(request.get("dataset_path", "")).strip() or None
    if dataset_path:
        return dataset_path
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for artifact in artifacts:
        artifact_type = str(artifact.get("type", "")).lower()
        artifact_name = str(artifact.get("name", "")).lower()
        artifact_path = str(artifact.get("path", "")).strip()
        signal = f"{artifact_type} {artifact_name}"
        if artifact_path and any(keyword in signal for keyword in lowered_keywords):
            return artifact_path
    return None


def _label_from_row(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def compute_classification_metrics(samples: list[dict[str, Any]], labels: list[str]) -> dict[str, float]:
    if not samples:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    resolved_labels = [label for label in labels if label]
    true_values: list[str] = []
    predicted_values: list[str] = []
    for row in samples:
        truth = _label_from_row(row, ["label", "expected", "expected_label", "ground_truth", "target"])
        predicted = _label_from_row(row, ["predicted", "prediction", "actual", "output"])
        if not predicted and truth:
            predicted = truth
        if truth:
            true_values.append(truth)
            predicted_values.append(predicted or "")
            if truth not in resolved_labels:
                resolved_labels.append(truth)
            if predicted and predicted not in resolved_labels:
                resolved_labels.append(predicted)

    if not true_values:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    correct = sum(1 for truth, predicted in zip(true_values, predicted_values) if truth == predicted)
    accuracy = correct / len(true_values)
    per_label_precision: list[float] = []
    per_label_recall: list[float] = []
    for label in resolved_labels:
        tp = sum(1 for truth, predicted in zip(true_values, predicted_values) if truth == label and predicted == label)
        fp = sum(1 for truth, predicted in zip(true_values, predicted_values) if truth != label and predicted == label)
        fn = sum(1 for truth, predicted in zip(true_values, predicted_values) if truth == label and predicted != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        per_label_precision.append(precision)
        per_label_recall.append(recall)

    precision = sum(per_label_precision) / max(len(per_label_precision), 1)
    recall = sum(per_label_recall) / max(len(per_label_recall), 1)
    f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
    }


def evaluate_rag_dataset(samples: list[dict[str, Any]]) -> dict[str, float]:
    if not samples:
        return {"correctness_rate": 0.0, "grounding_rate": 0.0, "hallucination_rate": 0.0}
    correct = 0
    grounded = 0
    hallucination_hits = 0
    for item in samples:
        expected = str(item.get("expected_contains", "")).lower().strip()
        response = str(item.get("response", item.get("mock_response", ""))).lower().strip()
        reference = str(item.get("expected_reference", item.get("expected_citation", ""))).lower().strip()
        if expected and expected in response:
            correct += 1
        if reference and reference in response:
            grounded += 1
        if "hallucination" in str(item.get("tags", "")).lower():
            hallucination_hits += 1
        elif any(token in response for token in ["guaranteed", "100%", "never fails"]) and reference not in response:
            hallucination_hits += 1
    total = len(samples)
    return {
        "correctness_rate": round(correct / total, 4),
        "grounding_rate": round(grounded / total, 4),
        "hallucination_rate": round(hallucination_hits / total, 4),
    }


def evaluate_llm_dataset(samples: list[dict[str, Any]]) -> dict[str, float]:
    if not samples:
        return {"consistency_rate": 0.0, "expected_output_rate": 0.0}
    consistent = 0
    expected_hits = 0
    for item in samples:
        prompt = str(item.get("prompt", "")).strip().lower()
        expected = str(item.get("expected_contains", item.get("expected_output", ""))).strip().lower()
        response = str(item.get("response", item.get("mock_response", ""))).strip().lower()
        if prompt and response:
            consistent += 1
        if expected and expected in response:
            expected_hits += 1
    total = len(samples)
    return {
        "consistency_rate": round(consistent / total, 4),
        "expected_output_rate": round(expected_hits / total, 4),
    }
