"""
Standalone script for PDF generation.
Runs as a subprocess so it has no shared asyncio loops or greenlets
with the parent Flask/Playwright process.

Usage: python pdf_worker.py <html_path> <output_path>
"""
import sys
from playwright.sync_api import sync_playwright

def main():
    if len(sys.argv) != 3:
        print("Usage: pdf_worker.py <html_path> <output_path>", file=sys.stderr)
        sys.exit(1)

    html_path   = sys.argv[1]
    output_path = sys.argv[2]

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.pdf(
            path=output_path,
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()

if __name__ == "__main__":
    main()
