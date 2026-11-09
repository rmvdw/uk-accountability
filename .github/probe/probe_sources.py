"""TEMPORARY (issue #13): locate and inspect ONS and Home Office immigration workbooks.

Runs on a GitHub runner. Writes probe-out/ with the raw files and a report of
sheet names and header rows, for writing source contracts. Removed before merge.
"""

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

import openpyxl

UA = {"User-Agent": "uk-accountability (+https://github.com/rmvdw/uk-accountability)"}
OUT = Path("probe-out")
OUT.mkdir(exist_ok=True)
report = []


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def inspect(path: Path, label: str) -> None:
    report.append(f"\n## {label}: {path.name} ({path.stat().st_size:,} bytes)")
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        report.append(f"cannot open: {exc}")
        return
    for ws in wb.worksheets:
        report.append(f"\n### sheet `{ws.title}` dims={ws.dimensions}")
        for i, row in enumerate(ws.iter_rows(max_row=14, values_only=True)):
            cells = [str(c)[:60] for c in row if c is not None]
            if cells:
                report.append(f"r{i + 1}: " + " | ".join(cells[:14]))


# --- ONS LTIM flows (provisional) -------------------------------------------
ons_page = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/"
    "internationalmigration/datasets/"
    "longterminternationalimmigrationemigrationandnetmigrationflowsprovisional"
)
page = get(ons_page).decode("utf-8", "replace")
links = sorted(set(re.findall(r'href="(/file\?uri=[^"]+?\.xlsx)"', page)))
report.append("# ONS dataset page xlsx links\n" + "\n".join(html.unescape(x) for x in links))
for href in links[:2]:
    url = "https://www.ons.gov.uk" + html.unescape(href)
    p = OUT / ("ons_" + url.rsplit("/", 1)[-1])
    p.write_bytes(get(url))
    report.append(f"\nfetched {url}")
    inspect(p, "ONS")

# --- Home Office immigration system statistics data tables -------------------
api = "https://www.gov.uk/api/content/government/statistical-data-sets/immigration-system-statistics-data-tables"
meta = json.loads(get(api))
atts = meta.get("details", {}).get("attachments", [])
report.append("\n# Home Office attachments (title | url)")
for a in atts:
    report.append(f"- {a.get('title')} | {a.get('url')} | {a.get('content_type')}")
wanted = re.compile(r"(asylum claims|initial decisions|awaiting|small boat|illegal entry|entry clearance visas granted|visas? granted|summary)", re.I)
picked = [a for a in atts if wanted.search(a.get("title", "")) and str(a.get("url", "")).endswith((".xlsx", ".ods"))]
report.append("\n# picked: " + ", ".join(a["title"] for a in picked))
for a in picked[:8]:
    url = a["url"]
    p = OUT / ("ho_" + url.rsplit("/", 1)[-1])
    data = get(url)
    p.write_bytes(data)
    report.append(f"\nfetched {url} ({len(data):,} bytes)")
    if p.suffix == ".xlsx":
        inspect(p, "Home Office: " + a["title"])

(OUT / "REPORT.md").write_text("\n".join(report) + "\n")
# Keep the repo small: drop very large workbooks from the commit, keep the report.
for f in OUT.iterdir():
    if f.suffix in (".xlsx", ".ods") and f.stat().st_size > 8_000_000:
        f.unlink()
print("\n".join(report)[:4000])
sys.exit(0)
