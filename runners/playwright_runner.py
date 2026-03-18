from __future__ import annotations

from pathlib import Path
from typing import Any


def _defect(defect_id: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "id": defect_id,
        "severity": severity,
        "message": message,
        "details": details,
    }


def run_web_smoke(
    url: str,
    auth: dict[str, Any],
    timeout_ms: int,
    screenshot_dir: str,
    browser: str = "chromium",
    headless: bool = True,
) -> dict[str, Any]:
    defects: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    screenshot_path: str | None = None

    if not url:
        return {
            "status": "failed",
            "passed": 0,
            "failed": 1,
            "defects": [_defect("web.missing_url", "high", "No URL/target provided for web execution")],
            "raw_output": {},
        }

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "failed",
            "passed": 0,
            "failed": 1,
            "defects": [_defect("web.playwright_import", "high", "Playwright import failed", error=str(exc))],
            "raw_output": {},
        }

    browser_instance = None
    try:
        with sync_playwright() as playwright:
            launcher = getattr(playwright, browser, playwright.chromium)
            browser_instance = launcher.launch(headless=headless)
            page = browser_instance.new_page()

            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response is not None and response.status < 400:
                passed += 1
            else:
                failed += 1
                status_code = None if response is None else response.status
                defects.append(
                    _defect(
                        "web.http_status",
                        "high",
                        "Navigation returned failing status",
                        status_code=status_code,
                        url=url,
                    )
                )

            if auth.get("required"):
                selector = auth.get("success_selector")
                if selector:
                    try:
                        page.wait_for_selector(selector, timeout=min(timeout_ms, 5000))
                        passed += 1
                    except Exception as exc:
                        failed += 1
                        defects.append(
                            _defect(
                                "web.auth_selector",
                                "high",
                                "Expected authenticated selector not found",
                                selector=selector,
                                error=str(exc),
                            )
                        )
                else:
                    failed += 1
                    defects.append(
                        _defect(
                            "web.auth_config",
                            "medium",
                            "Auth is required but no success selector is configured",
                        )
                    )

            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            screenshot_path = str(Path(screenshot_dir) / "web_last.png")
            page.screenshot(path=screenshot_path, full_page=True)

    except Exception as exc:
        failed += 1
        defects.append(_defect("web.execution_error", "critical", "Web execution failed", error=str(exc), url=url))
    finally:
        try:
            if browser_instance is not None:
                browser_instance.close()
        except Exception:
            pass

    status = "passed" if failed == 0 else "failed"
    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "defects": defects,
        "raw_output": {
            "url": url,
            "screenshot": screenshot_path,
            "timeout_ms": timeout_ms,
            "browser": browser,
        },
    }
