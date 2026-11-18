"""Regenerate the real knowledge base pages that come from the website's data files.

The website (CasavaianoWebsite) is the source of truth for apartments and nearby places: its
admin editor writes assets/js/data.js and assets/js/places.js. This script reads them with Node
and writes data/real/kb/appartamenti.md and dintorni.md. Run it after changing the site:

    uv run python scripts/import_site_kb.py --site ../CasavaianoWebsite
"""

import argparse
import json
import subprocess
from pathlib import Path

from casavaiano.config import DATA_DIR
from casavaiano.tools.live import load_lodgings

KB_OUT = DATA_DIR / "real" / "kb"
HEADER = (
    "<!-- Generated from the website by scripts/import_site_kb.py: edit the site, not here. -->"
)

NODE_DUMP = """
global.window = {};
const fs = require('fs');
for (const f of process.argv.slice(1)) eval(fs.readFileSync(f, 'utf8'));
process.stdout.write(JSON.stringify(
  {apartments: window.CV.apartments, booking: window.CV.BOOKING_URL, places: window.CV_PLACES}));
"""


def read_site(site: Path) -> dict:
    files = [str(site / "assets/js/data.js"), str(site / "assets/js/places.js")]
    out = subprocess.run(
        ["node", "-e", NODE_DUMP, *files], capture_output=True, text=True, encoding="utf-8"
    )
    if out.returncode:
        raise SystemExit(f"node failed: {out.stderr}")
    return json.loads(out.stdout)


def apartments_md(apartments: list[dict]) -> str:
    notes = {lodging.name: lodging.facts for lodging in load_lodgings()}
    parts = [
        HEADER,
        "# Gli appartamenti",
        "",
        "CasaVaiano ha otto alloggi: sette appartamenti e una casetta indipendente (Capanna).",
        "",
    ]
    for a in apartments:
        parts += [
            f"## {a['name']}",
            "",
            f"{a['floor']}, {a['size']} m². {a['tagline']}.",
            "",
            a["text"],
            "",
            f"Stanze: {'; '.join(a['rooms'])}.",
            "",
            f"Caratteristiche: {', '.join(a['tags'])}.",
        ]
        if a["name"] in notes:
            parts += ["", f"Note dei gestori: {notes[a['name']]}."]
        parts.append("")
    return "\n".join(parts)


def places_md(places: list[dict]) -> str:
    parts = [
        HEADER,
        "# Dintorni",
        "",
        "Luoghi da visitare vicino a CasaVaiano. Le distanze sono indicative, in auto.",
        "",
    ]
    for p in places:
        if p.get("km"):
            title = f"## {p['name']} (circa {p['km']} km)"
        elif p.get("group") == "vicino":
            title = f"## {p['name']} (a pochi minuti)"
        else:
            title = f"## {p['name']}"
        parts += [title, ""]
        for field in ("tagline", "intro", "text"):
            value = p.get(field)
            if value and value not in parts:
                parts += [value if value.endswith(".") else f"{value}.", ""]
        if p.get("highlights"):
            parts.append("Da non perdere:")
            parts += [f"- {h['name']}: {h['desc']}" for h in p["highlights"]]
            parts.append("")
        if p.get("official"):
            parts += [f"Sito ufficiale: {p['official']['name']}, {p['official']['url']}", ""]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("../CasavaianoWebsite"))
    site = read_site(parser.parse_args().site)
    KB_OUT.mkdir(parents=True, exist_ok=True)
    (KB_OUT / "appartamenti.md").write_text(apartments_md(site["apartments"]), encoding="utf-8")
    (KB_OUT / "dintorni.md").write_text(places_md(site["places"]), encoding="utf-8")
    print(f"{len(site['apartments'])} apartments, {len(site['places'])} places -> {KB_OUT}")


if __name__ == "__main__":
    main()
