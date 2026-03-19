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
```

## Project Layout

- `orchestrator/`: intake, classifier, planner, router, executor, reporter
- `adapters/`: pluggable test adapters per product type
- `runners/`: concrete test execution logic
- `schemas/`: YAML schemas for intake/result contracts
- `manifests/samples/`: sample manifests
