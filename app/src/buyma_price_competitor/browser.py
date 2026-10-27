from __future__ import annotations

from pathlib import Path
from playwright.async_api import Browser, BrowserContext, Page, Playwright


async def launch_chrome(
    playwright: Playwright,
    executable_paths: list[str],
    headless: bool,
    slow_mo: int,
    args: list[str] | None = None,
) -> tuple[Page, BrowserContext, Browser]:
    errors: list[str] = []
    for executable in executable_paths:
        path = Path(executable)
        if not path.exists():
            continue
        try:
            browser = await playwright.chromium.launch(
                headless=headless,
                executable_path=str(path),
                slow_mo=slow_mo,
                args=args or ["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context()
            page = await context.new_page()
            return page, context, browser
        except Exception as exc:
            errors.append(f"{executable}: {exc}")

    # Chromium fallback
    try:
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=args or ["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        page = await context.new_page()
        return page, context, browser
    except Exception as exc:
        errors.append(f"bundled chromium: {exc}")

    raise RuntimeError("Chrome 실행 실패:\n" + "\n".join(errors))
