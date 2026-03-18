from pathlib import Path

import pytest

from orchestrator.intake import load_manifest


def test_load_manifest_valid_sample() -> None:
    sample_path = Path("manifests/samples/web_booking.yaml")
    manifest = load_manifest(sample_path)
    assert manifest.project_type == "web"
    assert manifest.outputs["report_format"] == "json"


def test_load_manifest_missing_required_sections(tmp_path: Path) -> None:
    invalid_manifest = tmp_path / "invalid.yaml"
    invalid_manifest.write_text(
        """
name: invalid
project_type: web
artifacts: []
environment: {}
request: {}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_manifest(invalid_manifest)
