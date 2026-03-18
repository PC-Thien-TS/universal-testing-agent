from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestrator.classifier import classify_product
from orchestrator.config import ensure_runtime_dirs, load_runtime_config
from orchestrator.executor import execute_pipeline, load_execution_result, save_execution_result
from orchestrator.intake import load_and_normalize, load_manifest
from orchestrator.planner import generate_test_strategy
from orchestrator.reporter import generate_report, save_report
from orchestrator.router import select_adapter


def _resolve_output_path(explicit_path: str | None, default_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return Path(default_path)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def handle_validate_manifest(args: argparse.Namespace) -> int:
    try:
        load_manifest(args.manifest)
    except Exception as exc:
        _print_json({"status": "invalid", "manifest": args.manifest, "error": str(exc)})
        return 1
    _print_json({"status": "valid", "manifest": args.manifest})
    return 0


def handle_plan(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)

    intake = load_and_normalize(args.manifest)
    product_type = classify_product(intake)
    strategy = generate_test_strategy(intake, product_type)

    plan_path = _resolve_output_path(args.output, config.paths.latest_plan_file)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(strategy.model_dump(mode="json"), indent=2), encoding="utf-8")

    _print_json(
        {
            "status": "planned",
            "project_type": product_type,
            "manifest": args.manifest,
            "plan_file": str(plan_path),
            "plan": strategy.model_dump(mode="json"),
        }
    )
    return 0


def handle_run(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)

    intake = load_and_normalize(args.manifest)
    product_type = classify_product(intake)
    strategy = generate_test_strategy(intake, product_type)
    adapter = select_adapter(product_type, config)
    envelope = execute_pipeline(intake, product_type, strategy, adapter)

    result_path = _resolve_output_path(args.output, config.paths.latest_result_file)
    save_execution_result(envelope, result_path)

    _print_json(
        {
            "status": "completed",
            "manifest": args.manifest,
            "project_type": product_type,
            "adapter": adapter.name,
            "run_status": envelope.status,
            "result_file": str(result_path),
        }
    )
    return 0


def handle_report(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)

    envelope = load_execution_result(args.result_json)
    report = generate_report(envelope)

    report_path = _resolve_output_path(args.output, config.paths.latest_report_file)
    save_report(report, report_path)

    _print_json(
        {
            "status": "reported",
            "source_result": args.result_json,
            "report_file": str(report_path),
            "summary": report.summary,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uta", description="Universal Testing Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-manifest", help="Validate a manifest YAML file")
    validate_parser.add_argument("manifest", help="Path to manifest file")
    validate_parser.set_defaults(handler=handle_validate_manifest)

    plan_parser = subparsers.add_parser("plan", help="Generate a test strategy from manifest")
    plan_parser.add_argument("manifest", help="Path to manifest file")
    plan_parser.add_argument("--output", help="Output path for plan JSON", default=None)
    plan_parser.set_defaults(handler=handle_plan)

    run_parser = subparsers.add_parser("run", help="Execute tests via routed adapter")
    run_parser.add_argument("manifest", help="Path to manifest file")
    run_parser.add_argument("--output", help="Output path for execution result JSON", default=None)
    run_parser.set_defaults(handler=handle_run)

    report_parser = subparsers.add_parser("report", help="Generate standardized report from result JSON")
    report_parser.add_argument("result_json", help="Path to execution result JSON")
    report_parser.add_argument("--output", help="Output path for report JSON", default=None)
    report_parser.set_defaults(handler=handle_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
