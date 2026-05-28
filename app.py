import os
import threading
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from playwright.sync_api import sync_playwright

from generator import generate_pdf

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Background scraper — runs in a daemon thread, uses sync_playwright safely
# because it has its own OS thread (not sharing a loop with generator.py).
# ---------------------------------------------------------------------------

def _scrape_worker(url: str, results: dict, key: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            results[key] = page.title()
        finally:
            browser.close()


def scrape_title(url: str) -> str:
    results: dict = {}
    t = threading.Thread(target=_scrape_worker, args=(url, results, "title"), daemon=True)
    t.start()
    t.join(timeout=35)
    return results.get("title", "")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/scrape")
def scrape():
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url param required"}), 400
    title = scrape_title(url)
    return jsonify({"url": url, "title": title})


@app.post("/pdf")
def pdf():
    """
    Accepts JSON body: {"html": "<h1>Hello</h1>", "filename": "out.pdf"}
    Returns the generated PDF as an attachment.
    """
    data = request.get_json(force=True) or {}
    html = data.get("html", "<h1>Hello PDF</h1>")
    filename = data.get("filename", "output.pdf")

    tmp = Path(tempfile.mkdtemp()) / filename
    try:
        generate_pdf(html, str(tmp))
        return send_file(tmp, as_attachment=True, download_name=filename, mimetype="application/pdf")
    finally:
        # cleanup after Flask streams the file
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
