"""Bundle the built dashboard into one self-contained HTML file.

    cd dashboard && npm run build
    python -m src.export_static_dashboard

Writes data/dashboard_static.html.

Takes the Vite build output and inlines the CSS, the JS bundle and the current
slate snapshot into a single file with no external requests. That file opens
from disk, emails, or drops onto any static host, and it is what gets published
as a shareable snapshot.

Deliberately reuses the compiled React app rather than reimplementing the UI in
plain HTML: a second implementation would drift from the first the moment
either changed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import config

DIST = Path(config.ROOT) / "dashboard" / "dist"


def build(fragment: bool = True) -> str:
    index = DIST / "index.html"
    if not index.exists():
        raise SystemExit(
            f"No build at {DIST}. Run:  cd dashboard && npm install && npm run build"
        )

    html = index.read_text(encoding="utf-8")
    css_names = re.findall(r'href="[^"]*?/([^/"]+\.css)"', html)
    js_names = re.findall(r'src="[^"]*?/([^/"]+\.js)"', html)
    if not js_names:
        raise SystemExit("Could not find the JS bundle in the build output.")

    css = "\n".join(
        (DIST / "assets" / name).read_text(encoding="utf-8") for name in css_names
    )
    js = "\n".join(
        (DIST / "assets" / name).read_text(encoding="utf-8") for name in js_names
    )

    data_path = config.DATA_DIR / "dashboard.json"
    if not data_path.exists():
        raise SystemExit(
            f"No snapshot at {data_path}. Run:  python -m src.export_dashboard"
        )
    data = json.loads(data_path.read_text(encoding="utf-8"))

    # </script> anywhere inside the JSON would close the tag early.
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

    parts = [
        "<title>Football Predictor</title>",
        f"<style>\n{css}\n</style>",
        '<div id="root"></div>',
        f"<script>window.__DASHBOARD_DATA__ = {payload};</script>",
        f"<script type=\"module\">\n{js}\n</script>",
    ]
    body = "\n".join(parts)

    if fragment:
        return body
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "</head>\n<body style=\"margin:0\">\n" + body + "\n</body>\n</html>\n"
    )


def run(fragment: bool = False) -> str:
    config.ensure_dirs()
    out = config.DATA_DIR / ("dashboard_fragment.html" if fragment else "dashboard_static.html")
    out.write_text(build(fragment), encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"  wrote {out} ({size:.0f} KB, no external requests)")
    return str(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bundle a single-file dashboard.")
    parser.add_argument(
        "--fragment", action="store_true",
        help="emit body content only, for hosts that supply their own document shell",
    )
    args = parser.parse_args()
    run(args.fragment)
