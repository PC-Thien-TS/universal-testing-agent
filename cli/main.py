from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestrator.asset_generator import generate_assets
from orchestrator.classifier import classify_product
from orchestrator.config import RuntimeConfig, ensure_runtime_dirs, load_runtime_config
from orchestrator.executor import execute_pipeline, load_execution_result, save_execution_result
from orchestrator.intake import load_and_normalize, load_manifest
from orchestrator.observability import RunObserver
from orchestrator.planner import generate_test_strategy
from orchestrator.reporter import generate_report, save_markdown_report, save_report
from orchestrator.router import select_adapter


def _resolve_output_path(explicit_path: str | None, default_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return Path(default_path)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _observer(config: RuntimeConfig, command: str, manifest_path: str = "") -> RunObserver:
    return RunObserver(runs_dir=config.paths.runs_dir, command=command, manifest_path=manifest_path)


def handle_validate_manifest(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "validate-manifest", manifest_path=args.manifest)
    try:
        manifest = load_manifest(args.manifest)
        observer.update_context(project_name=manifest.name, project_type=manifest.project_type)
        observer.log("Manifest validation succeeded.")
        run_metadata = observer.finalize(status="valid")
        _print_json(
            {
                "status": "valid",
                "manifest": args.manifest,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Manifest validation failed: {exc}")
        run_metadata = observer.finalize(status="invalid")
        _print_json(
            {
                "status": "invalid",
                "manifest": args.manifest,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_plan(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "plan", manifest_path=args.manifest)
    try:
        intake = load_and_normalize(args.manifest)
        product_type = classify_product(intake)
        strategy = generate_test_strategy(intake, product_type)
        observer.update_context(project_name=intake.name, project_type=product_type)
        observer.log("Plan generated.")

        plan_path = _resolve_output_path(args.output, config.paths.latest_plan_file)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(strategy.model_dump(mode="json"), indent=2), encoding="utf-8")
        run_metadata = observer.finalize(status="planned")

        _print_json(
            {
                "status": "planned",
                "project_type": product_type,
                "manifest": args.manifest,
                "plan_file": str(plan_path),
                "plan": strategy.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Plan generation failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "manifest": args.manifest,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_generate_assets(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "generate-assets", manifest_path=args.manifest)
    try:
        intake = load_and_normalize(args.manifest)
        product_type = classify_product(intake)
        strategy = generate_test_strategy(intake, product_type)
        observer.update_context(project_name=intake.name, project_type=product_type)
        bundle = generate_assets(intake, product_type, strategy, config)
        observer.log("Asset generation completed.")
        run_metadata = observer.finalize(status="generated")
        _print_json(
            {
                "status": "generated",
                "manifest": args.manifest,
                "project_type": product_type,
                "artifacts": bundle.artifact_paths,
                "known_gaps": bundle.known_gaps,
                "assumptions": bundle.assumptions,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Asset generation failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "manifest": args.manifest,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_run(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "run", manifest_path=args.manifest)
    try:
        intake = load_and_normalize(args.manifest)
        product_type = classify_product(intake)
        strategy = generate_test_strategy(intake, product_type)
        adapter = select_adapter(product_type, config)
        observer.update_context(project_name=intake.name, project_type=product_type)
        observer.log(f"Executing adapter={adapter.name}.")
        envelope = execute_pipeline(
            intake,
            product_type,
            strategy,
            adapter,
            run_id=observer.run_id,
            started_at=observer.started_at,
        )

        run_metadata = observer.finalize(status=envelope.status)
        envelope.run_metadata = run_metadata
        envelope.metadata["run_observability"] = run_metadata.model_dump(mode="json")
        envelope.metadata["artifact_dir"] = run_metadata.artifact_dir

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
                "summary": envelope.summary.model_dump(mode="json"),
                "recommendation": envelope.recommendation.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Run command failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "manifest": args.manifest,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_report(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "report", manifest_path=args.result_json)
    try:
        envelope = load_execution_result(args.result_json)
        observer.update_context(project_name=envelope.project_name, project_type=envelope.project_type)
        report = generate_report(envelope)

        report_path = _resolve_output_path(args.output, config.paths.latest_report_file)
        markdown_path = _resolve_output_path(args.markdown_output, config.paths.latest_report_markdown_file)
        save_report(report, report_path)
        save_markdown_report(report, markdown_path)
        observer.log("Report generation completed.")
        run_metadata = observer.finalize(status="reported")

        _print_json(
            {
                "status": "reported",
                "source_result": args.result_json,
                "report_file": str(report_path),
                "markdown_report_file": str(markdown_path),
                "summary": report.summary.model_dump(mode="json"),
                "policy": report.policy.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Report command failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "source_result": args.result_json,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


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

    assets_parser = subparsers.add_parser("generate-assets", help="Generate checklist and testcase assets")
    assets_parser.add_argument("manifest", help="Path to manifest file")
    assets_parser.set_defaults(handler=handle_generate_assets)

    run_parser = subparsers.add_parser("run", help="Execute tests via routed adapter")
    run_parser.add_argument("manifest", help="Path to manifest file")
    run_parser.add_argument("--output", help="Output path for execution result JSON", default=None)
    run_parser.set_defaults(handler=handle_run)

    report_parser = subparsers.add_parser("report", help="Generate standardized report from result JSON")
    report_parser.add_argument("result_json", help="Path to execution result JSON")
    report_parser.add_argument("--output", help="Output path for report JSON", default=None)
    report_parser.add_argument("--markdown-output", help="Output path for report Markdown", default=None)
    report_parser.set_defaults(handler=handle_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
