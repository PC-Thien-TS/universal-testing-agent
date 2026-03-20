from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orchestrator.asset_generator import generate_assets
from orchestrator.classifier import classify_product
from orchestrator.compare import compare_results, save_comparison
from orchestrator.config import RuntimeConfig, ensure_runtime_dirs, load_runtime_config
from orchestrator.coverage_catalog import build_coverage_catalog, save_coverage_catalog
from orchestrator.contracts import save_contract_validation, validate_contracts
from orchestrator.executor import execute_pipeline, load_execution_result, save_execution_result
from orchestrator.history import load_history_records, persist_history_record, record_from_execution, record_from_report
from orchestrator.intake import load_and_normalize, load_manifest
from orchestrator.observability import RunObserver
from orchestrator.planner import generate_test_strategy
from orchestrator.plugin_onboarding import evaluate_plugin_onboarding, evaluate_registry_onboarding, scaffold_plugin
from orchestrator.registry import get_registry
from orchestrator.reporter import generate_report, save_markdown_report, save_report
from orchestrator.router import (
    adapter_capabilities,
    adapter_fallback_mode,
    adapter_fallback_note,
    adapter_plugin_inspection,
    select_adapter,
)
from orchestrator.models import PluginReportContext, PluginValidationSummary
from orchestrator.trends import analyze_trends, save_trends


def _resolve_output_path(explicit_path: str | None, default_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return Path(default_path)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _observer(config: RuntimeConfig, command: str, manifest_path: str = "") -> RunObserver:
    return RunObserver(runs_dir=config.paths.runs_dir, command=command, manifest_path=manifest_path)


def _persist_history_from_execution(envelope: Any, config: RuntimeConfig) -> str:
    record = record_from_execution(envelope)
    record_path = persist_history_record(record, config.paths.history_dir, config.paths.history_index_file)
    return str(record_path)


def _persist_history_from_report(report: Any, config: RuntimeConfig) -> str:
    record = record_from_report(report)
    record_path = persist_history_record(record, config.paths.history_dir, config.paths.history_index_file)
    return str(record_path)


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
        capabilities = adapter_capabilities(product_type)
        fallback_mode = adapter_fallback_mode(product_type)
        fallback_note = adapter_fallback_note(product_type)
        plugin_details = adapter_plugin_inspection(product_type)
        registry = get_registry()
        plugin_inspection = registry.inspection_for_product_type(product_type)
        onboarding = evaluate_plugin_onboarding(plugin_inspection, project_root=".")
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
        envelope.metadata["capabilities_used"] = capabilities
        envelope.metadata["taxonomy_coverage_focus"] = strategy.coverage_focus
        envelope.metadata["adapter_registry_fallback_mode"] = fallback_mode
        envelope.metadata["plugin_context"] = plugin_details
        envelope.capability_path_used = capabilities
        envelope.plugin = PluginReportContext.model_validate(
            {
                "plugin_name": plugin_details["plugin_name"],
                "plugin_version": plugin_details["plugin_version"],
                "supported_product_types": plugin_details["supported_product_types"],
                "supported_capabilities": plugin_details["supported_capabilities"],
                "fallback_mode": plugin_details["fallback_mode"],
                "adapter_target": plugin_details["adapter_target"],
                "health_metadata": plugin_details["health_metadata"],
                "discovered_from": plugin_details["discovered_from"],
            }
        )
        envelope.plugin_validation = PluginValidationSummary.model_validate(plugin_details["validation"])
        envelope.plugin_onboarding = onboarding
        envelope.support_level = plugin_inspection.validation.support_level
        if fallback_mode != "native" or fallback_note:
            envelope.metadata["fallback_execution_note"] = fallback_note or f"Adapter fallback mode active: {fallback_mode}"
        envelope.metadata["plugin_onboarding"] = onboarding.model_dump(mode="json")
        envelope.metadata["support_level"] = plugin_inspection.validation.support_level
        envelope.metadata["coverage_catalog_reference"] = config.paths.latest_coverage_catalog_file

        result_path = _resolve_output_path(args.output, config.paths.latest_result_file)
        save_execution_result(envelope, result_path)
        history_record_path = _persist_history_from_execution(envelope, config)

        _print_json(
            {
                "status": "completed",
                "manifest": args.manifest,
                "project_type": product_type,
                "adapter": adapter.name,
                "run_status": envelope.status,
                "result_file": str(result_path),
                "history_record_file": history_record_path,
                "summary": envelope.summary.model_dump(mode="json"),
                "recommendation": envelope.recommendation.model_dump(mode="json"),
                "plugin_used": plugin_details["plugin_name"],
                "plugin_version": plugin_details["plugin_version"],
                "capabilities": capabilities,
                "fallback_mode": fallback_mode,
                "support_level": plugin_inspection.validation.support_level,
                "plugin_onboarding": onboarding.model_dump(mode="json"),
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
        report = generate_report(envelope, config=config)

        report_path = _resolve_output_path(args.output, config.paths.latest_report_file)
        markdown_path = _resolve_output_path(args.markdown_output, config.paths.latest_report_markdown_file)
        save_report(report, report_path)
        save_markdown_report(report, markdown_path)
        observer.log("Report generation completed.")
        run_metadata = observer.finalize(status="reported")
        history_record_path = _persist_history_from_report(report, config)

        _print_json(
            {
                "status": "reported",
                "source_result": args.result_json,
                "report_file": str(report_path),
                "markdown_report_file": str(markdown_path),
                "history_record_file": history_record_path,
                "summary": report.summary.model_dump(mode="json"),
                "policy": report.policy.model_dump(mode="json"),
                "plugin": report.plugin.model_dump(mode="json") if report.plugin else None,
                "plugin_validation": report.plugin_validation.model_dump(mode="json")
                if report.plugin_validation
                else None,
                "plugin_onboarding": report.plugin_onboarding.model_dump(mode="json")
                if report.plugin_onboarding
                else None,
                "support_level": report.support_level,
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


def handle_trends(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "trends")
    try:
        records = load_history_records(config.paths.history_dir)
        trends = analyze_trends(records)
        json_path, md_path = save_trends(
            trends,
            config.paths.latest_trends_file,
            config.paths.latest_trends_markdown_file,
        )
        observer.log("Trend analysis generated.")
        run_metadata = observer.finalize(status="analyzed")
        _print_json(
            {
                "status": "analyzed",
                "trends_file": str(json_path),
                "trends_markdown_file": str(md_path),
                "trends": trends.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Trend analysis failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_validate_contract(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "validate-contract", manifest_path=args.manifest)
    try:
        result = validate_contracts(args.manifest, result_path=args.result)
        json_path, md_path = save_contract_validation(
            result,
            config.paths.latest_contract_validation_file,
            config.paths.latest_contract_validation_markdown_file,
        )
        observer.log("Contract validation completed.")
        run_metadata = observer.finalize(status=result.verdict)
        _print_json(
            {
                "status": "validated",
                "manifest": args.manifest,
                "result_file": str(json_path),
                "markdown_file": str(md_path),
                "contract_validation": result.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0 if result.release_ready else 0
    except Exception as exc:
        observer.log(f"Contract validation failed: {exc}")
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


def handle_compare(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "compare")
    try:
        comparison = compare_results(args.current_result, args.baseline_result)
        json_path, md_path = save_comparison(
            comparison,
            config.paths.latest_compare_file,
            config.paths.latest_compare_markdown_file,
        )
        observer.log("Comparison completed.")
        run_metadata = observer.finalize(status="compared")
        _print_json(
            {
                "status": "compared",
                "compare_file": str(json_path),
                "compare_markdown_file": str(md_path),
                "comparison": comparison.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"Compare command failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_list_plugins(args: argparse.Namespace) -> int:
    _ = args
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "list-plugins")
    try:
        registry = get_registry()
        inspections = registry.list_plugins(include_invalid=True)
        onboarding_results = {
            item.plugin_name: item.model_dump(mode="json") for item in evaluate_registry_onboarding(inspections, project_root=".")
        }
        plugins = []
        for inspection in inspections:
            summary = inspection.summary()
            summary["support_level"] = inspection.validation.support_level
            summary["missing_recommended_capabilities"] = inspection.validation.missing_recommended_capabilities
            summary["onboarding"] = onboarding_results.get(inspection.plugin.plugin_name)
            plugins.append(summary)
        capability_coverage = registry.capability_coverage_summary()
        observer.log("Plugin list generated.")
        run_metadata = observer.finalize(status="listed")
        _print_json(
            {
                "status": "listed",
                "plugins": plugins,
                "supported_product_types": registry.supported_product_types(),
                "capability_coverage_summary": capability_coverage,
                "conflicts": registry.conflicts(),
                "discovery_errors": registry.discovery_errors(),
                "onboarding_summary": list(onboarding_results.values()),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"list-plugins failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_inspect_plugin(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "inspect-plugin")
    try:
        registry = get_registry()
        inspection = registry.inspect_plugin(args.plugin_name)
        if inspection is None:
            observer.log(f"Plugin not found: {args.plugin_name}")
            run_metadata = observer.finalize(status="not_found")
            _print_json(
                {
                    "status": "not_found",
                    "plugin_name": args.plugin_name,
                    "run_id": run_metadata.run_id,
                    "artifact_dir": run_metadata.artifact_dir,
                }
            )
            return 1

        observer.log(f"Plugin inspected: {args.plugin_name}")
        onboarding = evaluate_plugin_onboarding(inspection, project_root=".")
        run_metadata = observer.finalize(status="inspected")
        _print_json(
            {
                "status": "inspected",
                "plugin_name": inspection.plugin.plugin_name,
                "plugin_version": inspection.plugin.plugin_version,
                "supported_product_types": inspection.plugin.supported_product_types,
                "supported_capabilities": inspection.plugin.supported_capabilities,
                "fallback_mode": inspection.plugin.fallback_mode,
                "adapter_target": inspection.plugin.adapter_target(),
                "discovered_from": inspection.plugin.discovered_from,
                "health_metadata": inspection.plugin.health_metadata,
                "validation": inspection.validation.model_dump(mode="json"),
                "onboarding": onboarding.model_dump(mode="json"),
                "support_level": inspection.validation.support_level,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"inspect-plugin failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_coverage_catalog(args: argparse.Namespace) -> int:
    _ = args
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "coverage-catalog")
    try:
        registry = get_registry()
        catalog = build_coverage_catalog(registry, project_root=".")
        json_path, md_path = save_coverage_catalog(
            catalog,
            config.paths.latest_coverage_catalog_file,
            config.paths.latest_coverage_catalog_markdown_file,
        )
        observer.log("Coverage catalog generated.")
        run_metadata = observer.finalize(status="generated")
        _print_json(
            {
                "status": "generated",
                "coverage_catalog_file": str(json_path),
                "coverage_catalog_markdown_file": str(md_path),
                "entries": [entry.model_dump(mode="json") for entry in catalog.entries],
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"coverage-catalog failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_scaffold_plugin(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "scaffold-plugin")
    try:
        result = scaffold_plugin(args.product_type, mode=args.mode, project_root=".")
        observer.log(f"Plugin scaffold generated for product_type={args.product_type}")
        run_metadata = observer.finalize(status="scaffolded")
        _print_json(
            {
                "status": "scaffolded",
                "product_type": args.product_type,
                "mode": args.mode,
                "created_files": result["created_files"],
                "skipped_files": result["skipped_files"],
                "capability_template": result["capability_template"],
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"scaffold-plugin failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "product_type": args.product_type,
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

    trends_parser = subparsers.add_parser("trends", help="Analyze trend history and emit trend reports")
    trends_parser.set_defaults(handler=handle_trends)

    contract_parser = subparsers.add_parser("validate-contract", help="Validate manifest/result contracts")
    contract_parser.add_argument("manifest", help="Path to manifest file")
    contract_parser.add_argument("--result", help="Optional result JSON path", default=None)
    contract_parser.set_defaults(handler=handle_validate_contract)

    compare_parser = subparsers.add_parser("compare", help="Compare current and baseline result files")
    compare_parser.add_argument("current_result", help="Path to current result JSON")
    compare_parser.add_argument("baseline_result", help="Path to baseline result JSON")
    compare_parser.set_defaults(handler=handle_compare)

    list_plugins_parser = subparsers.add_parser("list-plugins", help="List available adapter plugins")
    list_plugins_parser.set_defaults(handler=handle_list_plugins)

    inspect_plugin_parser = subparsers.add_parser("inspect-plugin", help="Inspect a specific plugin")
    inspect_plugin_parser.add_argument("plugin_name", help="Plugin name")
    inspect_plugin_parser.set_defaults(handler=handle_inspect_plugin)

    coverage_catalog_parser = subparsers.add_parser(
        "coverage-catalog",
        help="Generate plugin/product capability coverage catalog",
    )
    coverage_catalog_parser.set_defaults(handler=handle_coverage_catalog)

    scaffold_plugin_parser = subparsers.add_parser("scaffold-plugin", help="Scaffold plugin files for a product type")
    scaffold_plugin_parser.add_argument("product_type", help="Product type to scaffold")
    scaffold_plugin_parser.add_argument(
        "--mode",
        choices=["generic", "llm_like", "pipeline_like"],
        default="generic",
        help="Scaffold mode template",
    )
    scaffold_plugin_parser.set_defaults(handler=handle_scaffold_plugin)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
