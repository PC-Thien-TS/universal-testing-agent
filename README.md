# Universal Testing Agent

Universal Testing Agent (`uta`) is a manifest-driven AI testing orchestrator for web apps, APIs, and model endpoints.

## v1.1 Release Highlights

- Runnable CLI flow: `validate-manifest`, `plan`, `run`, `report`
- Orchestrator modules: intake, classifier, planner, router, executor, reporter
- Adapter coverage: web (Playwright), API (pytest), model (custom evaluator)
- Sample manifest included: `manifests/samples/web_booking.yaml`
- Test suite status: `pytest` passing

## v1.2 Release Highlights

- Standardized run-result contract across web/api/model adapters:
  - `run_id`, `project_name`, `project_type`, `adapter`, `status`, timing, `summary`, `coverage`, `defects`, `evidence`, `recommendation`
- Added sample manifests:
  - `manifests/samples/api_verify_store.yaml`
  - `manifests/samples/model_basalt.yaml`
- Improved planner with product-specific output:
  - Web priorities + constraints
  - API endpoint matrix + auth/contract/negative coverage focus
  - Model evaluation dimensions + metrics + threshold notes
- Added lightweight smoke execution hooks that are offline-friendly and deterministic when live systems are unavailable.
- `report` command now outputs both JSON and Markdown (`results/report_latest.md`).
- Expanded CLI integration tests to cover validate/plan/run/report flows for web/api/model manifests.

## v1.3 Release Highlights

- Observability for every CLI command with per-run artifacts in `results/runs/<run_id>/`:
  - `metadata.json`
  - `run.log`
- New policy/rule engine (`orchestrator/policy.py`) evaluating:
  - `blockers_allowed`
  - `critical_allowed`
  - `minimum_coverage`
  - `max_failed`
- New test asset generation (`generate-assets`) with standardized outputs:
  - `results/checklist_latest.json`
  - `results/checklist_latest.md`
  - `results/testcases_latest.json`
  - `results/testcases_latest.md`
  - `results/bug_report_template.md`
- Improved JSON/Markdown reports with:
  - policy evaluation
  - release gate summary
  - known gaps
  - assumptions
  - generated artifact references
- Extended tests for policy engine, asset generation, CLI asset command, run artifact directory creation, and policy-aware report output.

## v1.4 Release Highlights

- Added run history persistence under `results/history/` with indexed records:
  - per-record run summaries
  - `results/history/history_index.json`
- Added trend analytics (`orchestrator/trends.py`):
  - runs analyzed
  - overall/pass-rate/coverage/defect/release-readiness trends
  - outputs:
    - `results/trends_latest.json`
    - `results/trends_latest.md`
- Added contract validation module (`orchestrator/contracts.py`):
  - manifest contract checks by product type
  - result contract basics
  - API OpenAPI-like basics
  - model labels/dataset basics
  - outputs:
    - `results/contract_validation_latest.json`
    - `results/contract_validation_latest.md`
- Added comparison module (`orchestrator/compare.py`) and CLI command:
  - compare passed/failed/coverage/defects/release readiness
  - outputs:
    - `results/compare_latest.json`
    - `results/compare_latest.md`
- Extended report content with trend summary, contract summary, comparison summary, regression signals, and flaky suspicion notes.
- Added CLI commands:
  - `trends`
  - `validate-contract`
  - `compare`

## v1.5 Release Highlights

- Capability-driven orchestration foundation:
  - `orchestrator/capabilities.py` introduces a typed capability model for end-to-end testing workflows.
- Adapter registry:
  - `orchestrator/registry.py` maps product type -> adapter, supported capabilities, and fallback mode.
  - Supported product types now include:
    - `web`
    - `api`
    - `model`
    - `mobile`
    - `llm_app`
- Taxonomy engine:
  - `orchestrator/taxonomy.py` adds deterministic defaults for dimensions, risks, planning priorities, and coverage focus by product type.
  - Planner now uses taxonomy output for strategy generation.
- Manifest v2 draft support:
  - Added `schemas/manifest_v2.yaml`.
  - Intake supports both legacy manifests and v2-style manifests with `project.name/type/subtype`, interfaces, entry points, oracle, baseline, dependencies, and dimensions.
- New skeleton adapters:
  - `adapters/mobile_adapter.py`
  - `adapters/llm_app_adapter.py`
  - Both are deterministic, offline-safe smoke adapters with fallback behavior.
- New sample manifests:
  - `manifests/samples/mobile_app_smoke.yaml`
  - `manifests/samples/llm_app_eval.yaml`
- Reporting improvements:
  - Reports now include capabilities used, taxonomy coverage focus, and fallback execution notes when skeleton modes are active.
- Extended tests for:
  - registry behavior
  - taxonomy behavior
  - manifest v2 compatibility
  - classifier support for `mobile` and `llm_app`
  - new adapter behavior
  - CLI smoke flow for new manifests

## Requirements

- Python 3.11+
- Playwright browsers installed for web execution (`playwright install`)

## Install

```bash
pip install -e .
```

## Commands

```bash
uta validate-manifest manifests/samples/web_booking.yaml
uta plan manifests/samples/web_booking.yaml
uta generate-assets manifests/samples/web_booking.yaml
uta run manifests/samples/web_booking.yaml
uta report results/latest.json
uta trends
uta validate-contract manifests/samples/api_verify_store.yaml
uta compare results/latest.json results/latest.json
uta validate-manifest manifests/samples/mobile_app_smoke.yaml
uta validate-manifest manifests/samples/llm_app_eval.yaml
```

## Project Layout

- `orchestrator/`: intake, classifier, planner, router, executor, reporter
- `adapters/`: pluggable test adapters per product type
- `runners/`: concrete test execution logic
- `schemas/`: YAML schemas for intake/result contracts
- `manifests/samples/`: sample manifests
