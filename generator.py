"""
PDF generator using Playwright.

sync_playwright creates its own asyncio loop internally, which conflicts when
called from threads that already have a loop (or from the main thread when
another loop is running). The fix: use async_playwright directly and drive it
with a fresh, thread-local event loop that we create, run, and close ourselves.
"""

import asyncio
import threading
from pathlib import Path
from playwright.async_api import async_playwright


_local = threading.local()


def _get_thread_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop owned by the current thread."""
    loop = getattr(_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _local.loop = loop
    return loop


async def _generate_pdf(
    html: str,
    output_path: str,
    *,
    format: str = "A4",
    print_background: bool = True,
    margin: dict | None = None,
) -> None:
    if margin is None:
        margin = {"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.pdf(
                path=output_path,
                format=format,
                print_background=print_background,
                margin=margin,
            )
        finally:
            await browser.close()


def generate_pdf(
    html: str,
    output_path: str,
    *,
    format: str = "A4",
    print_background: bool = True,
    margin: dict | None = None,
) -> Path:
    """
    Generate a PDF from an HTML string and write it to *output_path*.

    Thread-safe: each thread gets its own asyncio event loop so there is
    no contention with the main Flask loop or other scraper threads.
    """
    loop = _get_thread_loop()
    loop.run_until_complete(
        _generate_pdf(
            html,
            output_path,
            format=format,
            print_background=print_background,
            margin=margin,
        )
    )
    return Path(output_path)
