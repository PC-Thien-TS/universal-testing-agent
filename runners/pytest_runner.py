from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _defect(defect_id: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "id": defect_id,
        "severity": severity,
        "message": message,
        "details": details,
    }


def _build_pytest_file(base_url: str, endpoints: list[str], timeout_s: int) -> str:
    return f'''import requests

BASE_URL = {base_url!r}
ENDPOINTS = {endpoints!r}
TIMEOUT_S = {timeout_s!r}


def test_api_smoke_endpoints():
    failures = []
    for endpoint in ENDPOINTS:
        url = BASE_URL.rstrip("/") + "/" + str(endpoint).lstrip("/")
        try:
            response = requests.get(url, timeout=TIMEOUT_S)
        except Exception as exc:
            failures.append(f"{{url}} request failed: {{exc}}")
            continue
        if response.status_code >= 500:
            failures.append(f"{{url}} returned 5xx: {{response.status_code}}")
    assert not failures, "; ".join(failures)
'''


def run_api_pytest(base_url: str, endpoints: list[str], timeout_s: int, pytest_args: list[str]) -> dict[str, Any]:
    if not base_url:
        return {
            "status": "failed",
            "passed": 0,
            "failed": 1,
            "defects": [_defect("api.missing_base_url", "high", "No base URL/target provided for API execution")],
            "raw_output": {},
        }

    normalized_endpoints = [str(item) for item in (endpoints or ["/"])]
    defects: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="uta-api-") as temp_dir:
        test_file = Path(temp_dir) / "test_api_smoke_generated.py"
        test_file.write_text(_build_pytest_file(base_url, normalized_endpoints, timeout_s), encoding="utf-8")

        command = [sys.executable, "-m", "pytest", str(test_file), *pytest_args]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(timeout_s * max(len(normalized_endpoints), 1), 5),
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "failed",
                "passed": 0,
                "failed": 1,
                "defects": [_defect("api.pytest_timeout", "critical", "Pytest execution timed out", timeout=str(exc.timeout))],
                "raw_output": {"command": command, "test_file": str(test_file)},
            }
        except Exception as exc:
            return {
                "status": "failed",
                "passed": 0,
                "failed": 1,
                "defects": [_defect("api.pytest_error", "critical", "Failed to execute pytest", error=str(exc))],
                "raw_output": {"command": command, "test_file": str(test_file)},
            }

        passed = 1 if completed.returncode == 0 else 0
        failed = 0 if completed.returncode == 0 else 1
        if completed.returncode != 0:
            defects.append(
                _defect(
                    "api.pytest_failed",
                    "high",
                    "Pytest API smoke test failed",
                    return_code=completed.returncode,
                )
            )

        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "passed": passed,
            "failed": failed,
            "defects": defects,
            "raw_output": {
                "command": command,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "test_file": str(test_file),
                "base_url": base_url,
                "endpoints": normalized_endpoints,
            },
        }
