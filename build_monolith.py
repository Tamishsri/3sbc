"""
build_monolith.py
-----------------
Compiles index.html by inlining styles.css, app.js, and candidates_data.json
into a single self-contained file for Vercel static deployment.

Firebase SDK is loaded from CDN (cannot be inlined), so CDN script tags stay in HTML.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).parent.resolve()


def read(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build():
    # ── Read source files ──────────────────────────────────────
    html_path = BASE / "index.html"
    css_path  = BASE / "styles.css"
    js_path   = BASE / "app.js"
    data_path = BASE / "candidates_data.json"

    for p in [html_path, css_path, js_path]:
        if not p.exists():
            print(f"[build] ERROR: {p} not found")
            return

    html = read(html_path)
    css  = read(css_path)
    js   = read(js_path)

    # ── Embed candidates_data.json ─────────────────────────────
    if data_path.exists():
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)
            embedded = json.dumps(candidates, ensure_ascii=False)
            print(f"[build] Embedding {len(candidates)} candidates")
        except Exception as e:
            print(f"[build] Warning: could not embed candidates: {e}")
            embedded = "[]"
    else:
        embedded = "[]"

    # Replace EMBEDDED_CANDIDATES placeholder
    html = html.replace(
        "window.EMBEDDED_CANDIDATES = []; // populated by build_monolith.py",
        f"window.EMBEDDED_CANDIDATES = {embedded};"
    )

    # ── Inline styles.css ──────────────────────────────────────
    html = html.replace(
        '<link rel="stylesheet" href="styles.css"/>',
        f'<style>\n{css}\n</style>'
    )

    # ── Inline app.js ──────────────────────────────────────────
    html = html.replace(
        '<script src="app.js"></script>',
        f'<script>\n{js}\n</script>'
    )

    # Remove external CSS/JS link stubs if any remain
    html = re.sub(r'<link\s+rel="stylesheet"\s+href="styles\.css"[^>]*/>', '', html)
    html = re.sub(r'<script\s+src="app\.js"[^>]*></script>', '', html)

    # ── Write output ──────────────────────────────────────────
    out_path = BASE / "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = round(len(html.encode("utf-8")) / 1024, 1)
    print(f"[build] [OK] Monolithic index.html compiled -- {size_kb} KB")
    print(f"[build]    Embedded candidates: {len(candidates) if data_path.exists() else 0}")
    print(f"[build]    CSS inlined:         {round(len(css.encode())/1024,1)} KB")
    print(f"[build]    JS inlined:          {round(len(js.encode())/1024,1)} KB")
    print(f"[build]    Firebase CDN tags:   kept (required for Auth + Firestore)")


if __name__ == "__main__":
    build()
