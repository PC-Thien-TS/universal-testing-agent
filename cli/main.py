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
from orchestrator.history_analyzer import analyze_history_intelligence, save_history_intelligence
from orchestrator.intake import load_and_normalize, load_manifest
from orchestrator.observability import RunObserver
from orchestrator.planner import generate_test_strategy
from orchestrator.plugin_onboarding import evaluate_plugin_onboarding, evaluate_registry_onboarding, scaffold_plugin
from orchestrator.plugin_packaging import export_plugin_package, import_plugin_package
from orchestrator.quality_gates import evaluate_quality_gates
from orchestrator.registry import get_registry
from orchestrator.compatibility import analyze_project_compatibility
from orchestrator.project_registry import get_project as get_registered_project
from orchestrator.reporter import (
    generate_report,
    save_ci_summary,
    save_junit_report,
    save_markdown_report,
    save_report,
)
from orchestrator.router import (
    adapter_capabilities,
    adapter_fallback_mode,
    adapter_fallback_note,
    adapter_plugin_inspection,
    select_adapter,
)
from orchestrator.models import EnvironmentConfig, PluginReportContext, PluginValidationSummary, RunRegistryRecord
from orchestrator.project_service import default_project_service
from orchestrator.platform_summary import summarize_platform_state
from orchestrator.trends import analyze_trends, save_trends
from orchestrator.run_registry import add_run_record


def _resolve_output_path(explicit_path: str | None, default_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return Path(default_path)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _gate_exit_code(gate_status: str | None) -> int:
    normalized = str(gate_status or "warning").lower()
    if normalized == "pass":
        return 0
    if normalized == "fail":
        return 2
    return 1


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


def _project_service(config: RuntimeConfig):
    return default_project_service(config.paths.project_registry_file, config.paths.run_registry_file)


def _project_paths(config: RuntimeConfig, project_id: str) -> dict[str, Path]:
    root = Path(config.paths.projects_dir) / project_id
    root.mkdir(parents=True, exist_ok=True)
    return {
        "root": root,
        "result": root / "latest.json",
        "report": root / "report_latest.json",
        "report_md": root / "report_latest.md",
        "ci": root / "ci_summary_latest.json",
        "junit": root / "report_latest.junit.xml",
        "quality_gates": root / "quality_gates_latest.json",
        "runs_dir": root / "runs",
    }


def _parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    return [item.strip() for item in raw_tags.split(",") if item.strip()]


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
                "author": plugin_details.get("author"),
                "dependencies": plugin_details.get("dependencies", []),
                "compatibility": plugin_details.get("compatibility", {}),
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
        contract_validation = validate_contracts(args.manifest, check_result_contract=False)
        envelope.metadata["contract_validation_summary"] = contract_validation.model_dump(mode="json")
        quality_gates = evaluate_quality_gates(
            acceptance=envelope.metadata.get("acceptance", {}),
            summary=envelope.summary,
            coverage=envelope.coverage,
            defects=envelope.defects,
            contract_validation=contract_validation,
            fallback_mode=fallback_mode,
        )
        envelope.quality_gates = quality_gates
        envelope.metadata["quality_gates"] = quality_gates.model_dump(mode="json")
        envelope.recommendation.release_ready = envelope.recommendation.release_ready and quality_gates.gate_status == "pass"
        quality_gate_path = Path(config.paths.latest_quality_gates_file)
        quality_gate_path.parent.mkdir(parents=True, exist_ok=True)
        quality_gate_path.write_text(json.dumps(quality_gates.model_dump(mode="json"), indent=2), encoding="utf-8")

        result_path = _resolve_output_path(args.output, config.paths.latest_result_file)
        save_execution_result(envelope, result_path)
        history_record_path = _persist_history_from_execution(envelope, config)
        gate_exit = _gate_exit_code(quality_gates.gate_status)

        report_path: str | None = None
        markdown_path: str | None = None
        ci_summary_path: str | None = None
        junit_path: str | None = None
        if bool(args.ci):
            report = generate_report(envelope, config=config)
            report_json_path = Path(config.paths.latest_report_file)
            report_md_path = Path(config.paths.latest_report_markdown_file)
            report_ci_path = Path(config.paths.latest_ci_summary_file)
            report_junit_path = Path(config.paths.latest_junit_file)
            save_report(report, report_json_path)
            save_markdown_report(report, report_md_path)
            save_ci_summary(report, report_ci_path)
            save_junit_report(report, report_junit_path)
            envelope.ci_summary = report.ci_summary
            save_execution_result(envelope, result_path)
            report_path = str(report_json_path)
            markdown_path = str(report_md_path)
            ci_summary_path = str(report_ci_path)
            junit_path = str(report_junit_path)
            observer.log(f"CI sidecar reports generated with gate_exit={gate_exit}.")

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
                "quality_gates": quality_gates.model_dump(mode="json"),
                "gate_exit_code": gate_exit,
                "ci_mode": bool(args.ci),
                "report_file": report_path,
                "markdown_report_file": markdown_path,
                "ci_summary_file": ci_summary_path,
                "junit_file": junit_path,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        if bool(args.ci) or bool(args.exit_on_fail):
            return gate_exit
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
        format_name = str(args.format or "json").lower()
        output_path = Path(args.output) if args.output else None
        markdown_path = _resolve_output_path(args.markdown_output, config.paths.latest_report_markdown_file)
        report_path: Path | None = None
        junit_path: Path | None = None
        ci_path: Path | None = None
        if format_name == "json":
            report_path = output_path or Path(config.paths.latest_report_file)
            save_report(report, report_path)
            save_markdown_report(report, markdown_path)
        elif format_name == "junit":
            junit_path = output_path or Path(config.paths.latest_junit_file)
            save_junit_report(report, junit_path)
            # keep markdown sidecar for human debugging
            save_markdown_report(report, markdown_path)
        elif format_name == "ci":
            ci_path = output_path or Path(config.paths.latest_ci_summary_file)
            save_ci_summary(report, ci_path)
            save_markdown_report(report, markdown_path)
        else:
            raise ValueError(f"Unsupported report format '{format_name}'.")

        if bool(args.ci):
            if ci_path is None:
                ci_path = Path(config.paths.latest_ci_summary_file)
                save_ci_summary(report, ci_path)
            if junit_path is None:
                junit_path = Path(config.paths.latest_junit_file)
                save_junit_report(report, junit_path)

        observer.log("Report generation completed.")
        run_metadata = observer.finalize(status="reported")
        history_record_path = _persist_history_from_report(report, config)
        gate_exit = _gate_exit_code(report.quality_gates.gate_status if report.quality_gates else None)
        effective_exit = gate_exit if bool(args.ci) or bool(args.exit_on_fail) or format_name in {"ci", "junit"} else 0

        _print_json(
            {
                "status": "reported",
                "format": format_name,
                "source_result": args.result_json,
                "report_file": str(report_path) if report_path else None,
                "junit_file": str(junit_path) if junit_path else None,
                "ci_summary_file": str(ci_path) if ci_path else None,
                "markdown_report_file": str(markdown_path) if markdown_path else None,
                "history_record_file": history_record_path,
                "summary": report.summary.model_dump(mode="json"),
                "policy": report.policy.model_dump(mode="json"),
                "quality_gates": report.quality_gates.model_dump(mode="json") if report.quality_gates else None,
                "plugin": report.plugin.model_dump(mode="json") if report.plugin else None,
                "plugin_validation": report.plugin_validation.model_dump(mode="json")
                if report.plugin_validation
                else None,
                "plugin_onboarding": report.plugin_onboarding.model_dump(mode="json")
                if report.plugin_onboarding
                else None,
                "support_level": report.support_level,
                "project_id": report.project_id,
                "environment_summary": report.environment_summary,
                "history_intelligence": report.history_intelligence.model_dump(mode="json")
                if report.history_intelligence
                else None,
                "regression_detected": report.regression_detected,
                "flaky_summary": report.flaky_summary,
                "dataset_evaluation_summary": report.dataset_evaluation_summary,
                "ci_mode": bool(args.ci),
                "exit_code": gate_exit,
                "effective_exit_code": effective_exit,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return effective_exit
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
        history_intelligence = analyze_history_intelligence(records)
        json_path, md_path = save_trends(
            trends,
            config.paths.latest_trends_file,
            config.paths.latest_trends_markdown_file,
        )
        intelligence_json_path, intelligence_md_path = save_history_intelligence(
            history_intelligence,
            config.paths.latest_history_intelligence_file,
            config.paths.latest_history_intelligence_markdown_file,
        )
        observer.log("Trend analysis generated.")
        run_metadata = observer.finalize(status="analyzed")
        _print_json(
            {
                "status": "analyzed",
                "trends_file": str(json_path),
                "trends_markdown_file": str(md_path),
                "trends": trends.model_dump(mode="json"),
                "history_intelligence_file": str(intelligence_json_path),
                "history_intelligence_markdown_file": str(intelligence_md_path),
                "history_intelligence": history_intelligence.model_dump(mode="json"),
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
                "author": inspection.plugin.author,
                "dependencies": inspection.plugin.dependencies,
                "compatibility": inspection.plugin.compatibility,
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


def handle_evaluate_gates(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "evaluate-gates", manifest_path=args.result_json)
    try:
        envelope = load_execution_result(args.result_json)
        observer.update_context(project_name=envelope.project_name, project_type=envelope.project_type)
        manifest_path = args.manifest or envelope.metadata.get("manifest_path")
        contract_validation = None
        if isinstance(manifest_path, str) and manifest_path.strip() and Path(manifest_path).exists():
            contract_validation = validate_contracts(manifest_path, check_result_contract=False)

        gates = evaluate_quality_gates(
            acceptance=envelope.metadata.get("acceptance", {}),
            summary=envelope.summary,
            coverage=envelope.coverage,
            defects=envelope.defects,
            contract_validation=contract_validation,
            fallback_mode=str(envelope.metadata.get("adapter_registry_fallback_mode", "native")),
        )
        gate_path = _resolve_output_path(args.output, config.paths.latest_quality_gates_file)
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        gate_path.write_text(json.dumps(gates.model_dump(mode="json"), indent=2), encoding="utf-8")
        observer.log("Quality gate evaluation completed.")
        run_metadata = observer.finalize(status=gates.gate_status)
        exit_code = _gate_exit_code(gates.gate_status)
        _print_json(
            {
                "status": "evaluated",
                "result_json": args.result_json,
                "manifest": manifest_path,
                "quality_gates_file": str(gate_path),
                "quality_gates": gates.model_dump(mode="json"),
                "exit_code": exit_code,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return exit_code
    except Exception as exc:
        observer.log(f"evaluate-gates failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "result_json": args.result_json,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_export_plugin(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "export-plugin")
    try:
        registry = get_registry()
        output = args.output or config.paths.latest_plugin_packages_dir
        package_path, payload = export_plugin_package(registry, args.plugin_name, output)
        observer.log(f"Plugin exported: {args.plugin_name}")
        run_metadata = observer.finalize(status="exported")
        _print_json(
            {
                "status": "exported",
                "plugin_name": args.plugin_name,
                "package_file": str(package_path),
                "metadata": payload,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"export-plugin failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "plugin_name": args.plugin_name,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_import_plugin(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "import-plugin")
    try:
        import_dir = args.target_dir or config.paths.latest_imported_plugins_dir
        import_path, payload, errors = import_plugin_package(args.path, import_dir)
        observer.log(f"Plugin package imported from {args.path}")
        run_metadata = observer.finalize(status="imported" if not errors else "import_warning")
        _print_json(
            {
                "status": "imported" if not errors else "warning",
                "source_package": args.path,
                "import_file": str(import_path),
                "import_errors": errors,
                "metadata": payload,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0 if not errors else 1
    except Exception as exc:
        observer.log(f"import-plugin failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "source_package": args.path,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_create_project(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "create-project", manifest_path=args.manifest)
    try:
        service = _project_service(config)
        project = service.create_project_from_manifest(
            name=args.name,
            manifest_path=args.manifest,
            product_type=args.type,
            project_id=args.project_id,
            description=args.description or "",
            tags=_parse_tags(args.tags),
            active=not bool(args.inactive),
        )
        compatibility = analyze_project_compatibility(project, environment_name="default")
        observer.update_context(project_name=project.name, project_type=project.product_type)
        run_metadata = observer.finalize(status="created")
        _print_json(
            {
                "status": "created",
                "project": project.model_dump(mode="json"),
                "compatibility": compatibility.model_dump(mode="json"),
                "project_registry_file": config.paths.project_registry_file,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"create-project failed: {exc}")
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


def handle_list_projects(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "list-projects")
    try:
        service = _project_service(config)
        projects = service.list_projects(active_only=bool(args.active_only))
        run_metadata = observer.finalize(status="listed")
        _print_json(
            {
                "status": "listed",
                "projects": [item.model_dump(mode="json") for item in projects],
                "project_registry_file": config.paths.project_registry_file,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"list-projects failed: {exc}")
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


def handle_inspect_project(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "inspect-project")
    try:
        service = _project_service(config)
        project = service.inspect_project(args.project_id)
        if project is None:
            run_metadata = observer.finalize(status="not_found")
            _print_json(
                {
                    "status": "not_found",
                    "project_id": args.project_id,
                    "run_id": run_metadata.run_id,
                    "artifact_dir": run_metadata.artifact_dir,
                }
            )
            return 1
        compatibility = analyze_project_compatibility(project, environment_name=args.environment or "default")
        recent_runs = service.list_runs(project.project_id, limit=5)
        observer.update_context(project_name=project.name, project_type=project.product_type)
        run_metadata = observer.finalize(status="inspected")
        _print_json(
            {
                "status": "inspected",
                "project": project.model_dump(mode="json"),
                "compatibility": compatibility.model_dump(mode="json"),
                "recent_runs": [item.model_dump(mode="json") for item in recent_runs],
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"inspect-project failed: {exc}")
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


def handle_run_project(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    service = _project_service(config)
    project = service.inspect_project(args.project_id)
    paths = _project_paths(config, args.project_id)
    observer = RunObserver(
        runs_dir=paths["runs_dir"],
        command="run-project",
        manifest_path=project.default_manifest_path if project else "",
    )
    try:
        if project is None:
            raise ValueError(f"Project '{args.project_id}' is not registered.")

        environment_name = args.environment or "default"
        intake = load_and_normalize(project.default_manifest_path)
        intake.name = project.name
        intake.project_type = project.product_type
        environment_override = project.environments.get(environment_name, {})
        if isinstance(environment_override, dict) and environment_override:
            environment_config = EnvironmentConfig.model_validate(environment_override)
            intake.environment_config = environment_config
            intake.environment = environment_config.model_dump(mode="json")
            if environment_config.base_url:
                intake.target = environment_config.base_url

        product_type = project.product_type if project.product_type != "auto" else classify_product(intake)
        strategy = generate_test_strategy(intake, product_type)
        adapter = select_adapter(product_type, config)
        capabilities = adapter_capabilities(product_type)
        fallback_mode = adapter_fallback_mode(product_type)
        fallback_note = adapter_fallback_note(product_type)
        plugin_details = adapter_plugin_inspection(product_type)
        registry = get_registry()
        plugin_inspection = registry.inspection_for_product_type(product_type)
        onboarding = evaluate_plugin_onboarding(plugin_inspection, project_root=".")
        compatibility = analyze_project_compatibility(project, environment_name=environment_name)

        observer.update_context(project_name=project.name, project_type=product_type, manifest_path=project.default_manifest_path)
        observer.log(f"Executing project adapter={adapter.name}.")
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
        envelope.project_id = project.project_id
        envelope.project_tags = list(project.tags)
        envelope.environment_name = environment_name
        envelope.compatibility_summary = compatibility.model_dump(mode="json")
        envelope.metadata["project_id"] = project.project_id
        envelope.metadata["project_name"] = project.name
        envelope.metadata["project_tags"] = list(project.tags)
        envelope.metadata["project_compatibility"] = compatibility.model_dump(mode="json")
        envelope.metadata["project_artifacts_root"] = str(paths["root"])
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
                "author": plugin_details.get("author"),
                "dependencies": plugin_details.get("dependencies", []),
                "compatibility": plugin_details.get("compatibility", {}),
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

        contract_validation = validate_contracts(project.default_manifest_path, check_result_contract=False)
        envelope.metadata["contract_validation_summary"] = contract_validation.model_dump(mode="json")
        quality_gates = evaluate_quality_gates(
            acceptance=envelope.metadata.get("acceptance", {}),
            summary=envelope.summary,
            coverage=envelope.coverage,
            defects=envelope.defects,
            contract_validation=contract_validation,
            fallback_mode=fallback_mode,
        )
        envelope.quality_gates = quality_gates
        envelope.metadata["quality_gates"] = quality_gates.model_dump(mode="json")
        envelope.recommendation.release_ready = envelope.recommendation.release_ready and quality_gates.gate_status == "pass"

        quality_gate_path = paths["quality_gates"]
        quality_gate_path.parent.mkdir(parents=True, exist_ok=True)
        quality_gate_path.write_text(json.dumps(quality_gates.model_dump(mode="json"), indent=2), encoding="utf-8")

        result_path = Path(args.output) if args.output else paths["result"]
        save_execution_result(envelope, result_path)
        history_record_path = _persist_history_from_execution(envelope, config)
        gate_exit = _gate_exit_code(quality_gates.gate_status)

        report = generate_report(envelope, config=config)
        report_json_path = paths["report"]
        report_md_path = paths["report_md"]
        report_ci_path = paths["ci"]
        report_junit_path = paths["junit"]
        save_report(report, report_json_path)
        save_markdown_report(report, report_md_path)
        if bool(args.ci):
            save_ci_summary(report, report_ci_path)
            save_junit_report(report, report_junit_path)
        envelope.ci_summary = report.ci_summary
        save_execution_result(envelope, result_path)

        report_paths = {
            "result_json": str(result_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
        }
        if bool(args.ci):
            report_paths["ci_summary"] = str(report_ci_path)
            report_paths["junit"] = str(report_junit_path)

        run_record = RunRegistryRecord(
            run_id=envelope.run_id,
            project_id=project.project_id,
            product_type=product_type,
            manifest_path=project.default_manifest_path,
            environment_name=environment_name,
            environment_type=str(envelope.metadata.get("environment_type")) if envelope.metadata.get("environment_type") else None,
            started_at=envelope.started_at,
            finished_at=envelope.finished_at,
            status=envelope.status,
            gate_status=quality_gates.gate_status,
            report_paths=report_paths,
            artifact_dir=run_metadata.artifact_dir,
            plugin_used=plugin_details["plugin_name"],
            summary=envelope.summary,
            coverage=envelope.coverage,
            defects=envelope.defects,
        )
        add_run_record(config.paths.run_registry_file, run_record)

        _print_json(
            {
                "status": "completed",
                "project_id": project.project_id,
                "project_name": project.name,
                "manifest": project.default_manifest_path,
                "environment_name": environment_name,
                "project_type": product_type,
                "adapter": adapter.name,
                "run_status": envelope.status,
                "result_file": str(result_path),
                "report_file": str(report_json_path),
                "report_markdown_file": str(report_md_path),
                "history_record_file": history_record_path,
                "run_registry_file": config.paths.run_registry_file,
                "summary": envelope.summary.model_dump(mode="json"),
                "recommendation": envelope.recommendation.model_dump(mode="json"),
                "plugin_used": plugin_details["plugin_name"],
                "plugin_version": plugin_details["plugin_version"],
                "compatibility": compatibility.model_dump(mode="json"),
                "quality_gates": quality_gates.model_dump(mode="json"),
                "gate_exit_code": gate_exit,
                "ci_mode": bool(args.ci),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        if bool(args.ci) or bool(args.exit_on_fail):
            return gate_exit
        return 0
    except Exception as exc:
        observer.log(f"run-project failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "project_id": args.project_id,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_list_runs(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "list-runs")
    try:
        service = _project_service(config)
        project = get_registered_project(config.paths.project_registry_file, args.project_id)
        if project is None:
            run_metadata = observer.finalize(status="not_found")
            _print_json(
                {
                    "status": "not_found",
                    "project_id": args.project_id,
                    "run_id": run_metadata.run_id,
                    "artifact_dir": run_metadata.artifact_dir,
                }
            )
            return 1
        runs = service.list_runs(args.project_id, limit=args.limit)
        observer.update_context(project_name=project.name, project_type=project.product_type)
        run_metadata = observer.finalize(status="listed")
        _print_json(
            {
                "status": "listed",
                "project_id": args.project_id,
                "runs": [item.model_dump(mode="json") for item in runs],
                "run_registry_file": config.paths.run_registry_file,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"list-runs failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "project_id": args.project_id,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_project_summary(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "project-summary")
    try:
        service = _project_service(config)
        summary = service.project_summary(args.project_id)
        if summary is None:
            run_metadata = observer.finalize(status="not_found")
            _print_json(
                {
                    "status": "not_found",
                    "project_id": args.project_id,
                    "run_id": run_metadata.run_id,
                    "artifact_dir": run_metadata.artifact_dir,
                }
            )
            return 1
        platform_state = summarize_platform_state(service)
        output_path = Path(args.output) if args.output else Path(config.paths.latest_project_summary_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8")
        run_metadata = observer.finalize(status="summarized")
        _print_json(
            {
                "status": "summarized",
                "project_id": args.project_id,
                "summary_file": str(output_path),
                "project_summary": summary.model_dump(mode="json"),
                "platform_summary": platform_state.model_dump(mode="json"),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"project-summary failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "project_id": args.project_id,
                "error": str(exc),
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 1


def handle_project_trends(args: argparse.Namespace) -> int:
    config = load_runtime_config()
    ensure_runtime_dirs(config)
    observer = _observer(config, "project-trends")
    try:
        service = _project_service(config)
        payload = service.project_trends(args.project_id)
        if payload is None:
            run_metadata = observer.finalize(status="not_found")
            _print_json(
                {
                    "status": "not_found",
                    "project_id": args.project_id,
                    "run_id": run_metadata.run_id,
                    "artifact_dir": run_metadata.artifact_dir,
                }
            )
            return 1
        output_path = Path(args.output) if args.output else Path(config.paths.latest_project_trends_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        run_metadata = observer.finalize(status="analyzed")
        _print_json(
            {
                "status": "analyzed",
                "project_id": args.project_id,
                "project_trends_file": str(output_path),
                "project_trends": payload,
                "run_id": run_metadata.run_id,
                "artifact_dir": run_metadata.artifact_dir,
            }
        )
        return 0
    except Exception as exc:
        observer.log(f"project-trends failed: {exc}")
        run_metadata = observer.finalize(status="error")
        _print_json(
            {
                "status": "error",
                "project_id": args.project_id,
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
    run_parser.add_argument("--ci", action="store_true", help="Enable CI mode sidecar outputs and gate-based exit codes")
    run_parser.add_argument("--exit-on-fail", action="store_true", help="Return quality-gate exit code for CI pipelines")
    run_parser.set_defaults(handler=handle_run)

    create_project_parser = subparsers.add_parser("create-project", help="Register a reusable project")
    create_project_parser.add_argument("--name", required=True, help="Project display name")
    create_project_parser.add_argument("--manifest", required=True, help="Default manifest path")
    create_project_parser.add_argument("--type", default=None, help="Optional product type override")
    create_project_parser.add_argument("--project-id", default=None, help="Project identifier")
    create_project_parser.add_argument("--description", default="", help="Project description")
    create_project_parser.add_argument("--tags", default="", help="Comma-separated tags")
    create_project_parser.add_argument("--inactive", action="store_true", help="Register project as inactive")
    create_project_parser.set_defaults(handler=handle_create_project)

    list_projects_parser = subparsers.add_parser("list-projects", help="List registered projects")
    list_projects_parser.add_argument("--active-only", action="store_true", help="Return only active projects")
    list_projects_parser.set_defaults(handler=handle_list_projects)

    inspect_project_parser = subparsers.add_parser("inspect-project", help="Inspect a project and compatibility details")
    inspect_project_parser.add_argument("project_id", help="Project identifier")
    inspect_project_parser.add_argument("--environment", default=None, help="Environment name override")
    inspect_project_parser.set_defaults(handler=handle_inspect_project)

    run_project_parser = subparsers.add_parser("run-project", help="Execute using a registered project")
    run_project_parser.add_argument("project_id", help="Project identifier")
    run_project_parser.add_argument("--environment", default="default", help="Environment name")
    run_project_parser.add_argument("--output", default=None, help="Optional result JSON path")
    run_project_parser.add_argument("--ci", action="store_true", help="Enable CI mode sidecar outputs and gate-based exit codes")
    run_project_parser.add_argument("--exit-on-fail", action="store_true", help="Return quality-gate exit code for CI pipelines")
    run_project_parser.set_defaults(handler=handle_run_project)

    list_runs_parser = subparsers.add_parser("list-runs", help="List runs for a registered project")
    list_runs_parser.add_argument("project_id", help="Project identifier")
    list_runs_parser.add_argument("--limit", type=int, default=20, help="Maximum runs to return")
    list_runs_parser.set_defaults(handler=handle_list_runs)

    project_summary_parser = subparsers.add_parser("project-summary", help="Summarize project quality and recent status")
    project_summary_parser.add_argument("project_id", help="Project identifier")
    project_summary_parser.add_argument("--output", default=None, help="Optional output path for summary JSON")
    project_summary_parser.set_defaults(handler=handle_project_summary)

    project_trends_parser = subparsers.add_parser("project-trends", help="Analyze trend signals for one project")
    project_trends_parser.add_argument("project_id", help="Project identifier")
    project_trends_parser.add_argument("--output", default=None, help="Optional output path for trends JSON")
    project_trends_parser.set_defaults(handler=handle_project_trends)

    report_parser = subparsers.add_parser("report", help="Generate standardized report from result JSON")
    report_parser.add_argument("result_json", help="Path to execution result JSON")
    report_parser.add_argument("--output", help="Output path for report JSON", default=None)
    report_parser.add_argument("--markdown-output", help="Output path for report Markdown", default=None)
    report_parser.add_argument("--format", choices=["json", "junit", "ci"], default="json", help="Report output format")
    report_parser.add_argument("--ci", action="store_true", help="Enable CI mode sidecar outputs and gate-based exit codes")
    report_parser.add_argument("--exit-on-fail", action="store_true", help="Return quality-gate exit code for CI pipelines")
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

    evaluate_gates_parser = subparsers.add_parser("evaluate-gates", help="Evaluate quality gates for a run result")
    evaluate_gates_parser.add_argument("result_json", help="Path to execution result JSON")
    evaluate_gates_parser.add_argument("--manifest", help="Optional manifest path override", default=None)
    evaluate_gates_parser.add_argument("--output", help="Output path for quality gate JSON", default=None)
    evaluate_gates_parser.set_defaults(handler=handle_evaluate_gates)

    export_plugin_parser = subparsers.add_parser("export-plugin", help="Export plugin metadata package")
    export_plugin_parser.add_argument("plugin_name", help="Plugin name")
    export_plugin_parser.add_argument("--output", help="Output file or directory", default=None)
    export_plugin_parser.set_defaults(handler=handle_export_plugin)

    import_plugin_parser = subparsers.add_parser("import-plugin", help="Import plugin metadata package")
    import_plugin_parser.add_argument("path", help="Path to exported plugin package JSON")
    import_plugin_parser.add_argument("--target-dir", help="Target directory for imported package records", default=None)
    import_plugin_parser.set_defaults(handler=handle_import_plugin)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
