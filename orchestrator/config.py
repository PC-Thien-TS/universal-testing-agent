from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class PathSettings(BaseModel):
    results_dir: str = "results"
    evidence_dir: str = "evidence"
    latest_result_file: str = "results/latest.json"
    latest_plan_file: str = "results/plan_latest.json"
    latest_report_file: str = "results/report_latest.json"
    latest_report_markdown_file: str = "results/report_latest.md"


class TimeoutSettings(BaseModel):
    web_ms: int = 8000
    api_s: int = 10
    model_s: int = 20


class WebRunnerSettings(BaseModel):
    browser: str = "chromium"
    headless: bool = True


class ApiRunnerSettings(BaseModel):
    pytest_args: list[str] = Field(default_factory=lambda: ["-q", "--disable-warnings", "--maxfail=1"])


class ModelRunnerSettings(BaseModel):
    default_threshold: float = 0.7


class RunnerSettings(BaseModel):
    web: WebRunnerSettings = Field(default_factory=WebRunnerSettings)
    api: ApiRunnerSettings = Field(default_factory=ApiRunnerSettings)
    model: ModelRunnerSettings = Field(default_factory=ModelRunnerSettings)


class RuntimeConfig(BaseModel):
    paths: PathSettings = Field(default_factory=PathSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)
    runners: RunnerSettings = Field(default_factory=RunnerSettings)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def load_runtime_config(config_path: str | Path | None = None) -> RuntimeConfig:
    resolved_path = Path(config_path or os.getenv("UTA_CONFIG_PATH", "configs/default.yaml"))
    config = RuntimeConfig.model_validate(_read_yaml(resolved_path))

    if value := os.getenv("UTA_RESULTS_FILE"):
        config.paths.latest_result_file = value
    if value := os.getenv("UTA_PLAN_FILE"):
        config.paths.latest_plan_file = value
    if value := os.getenv("UTA_REPORT_FILE"):
        config.paths.latest_report_file = value
    if value := os.getenv("UTA_REPORT_MD_FILE"):
        config.paths.latest_report_markdown_file = value
    if value := os.getenv("UTA_EVIDENCE_DIR"):
        config.paths.evidence_dir = value
    if value := os.getenv("UTA_TIMEOUT_WEB_MS"):
        config.timeouts.web_ms = int(value)
    if value := os.getenv("UTA_TIMEOUT_API_S"):
        config.timeouts.api_s = int(value)
    if value := os.getenv("UTA_TIMEOUT_MODEL_S"):
        config.timeouts.model_s = int(value)

    return config


def ensure_runtime_dirs(config: RuntimeConfig) -> None:
    Path(config.paths.results_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.evidence_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.latest_result_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config.paths.latest_plan_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config.paths.latest_report_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config.paths.latest_report_markdown_file).parent.mkdir(parents=True, exist_ok=True)
