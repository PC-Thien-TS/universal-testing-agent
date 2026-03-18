# Universal Testing Agent

Universal Testing Agent (`uta`) is a manifest-driven AI testing orchestrator for web apps, APIs, and model endpoints.

## v1.1 Release Highlights

- Runnable CLI flow: `validate-manifest`, `plan`, `run`, `report`
- Orchestrator modules: intake, classifier, planner, router, executor, reporter
- Adapter coverage: web (Playwright), API (pytest), model (custom evaluator)
- Sample manifest included: `manifests/samples/web_booking.yaml`
- Test suite status: `pytest` passing

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
uta run manifests/samples/web_booking.yaml
uta report results/latest.json
```

## Project Layout

- `orchestrator/`: intake, classifier, planner, router, executor, reporter
- `adapters/`: pluggable test adapters per product type
- `runners/`: concrete test execution logic
- `schemas/`: YAML schemas for intake/result contracts
- `manifests/samples/`: sample manifests
