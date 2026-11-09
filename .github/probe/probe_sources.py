"""TEMPORARY (issue #13): fetch the target workbooks and dump their structure."""

import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl

UA = {"User-Agent": "uk-accountability (+https://github.com/rmvdw/uk-accountability)"}
OUT = Path("probe-out")
OUT.mkdir(exist_ok=True)
ONS = (
    "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/populationandmigration/"
    "internationalmigration/datasets/longterminternationalimmigrationemigrationandnetmigrationflowsprovisional/"
)
TARGETS = {
    "ons_ye_dec2025.xlsx": ONS + "yearendingdecember2025/may2026publicationspreadsheet.xlsx",
    "ons_ye_jun2025.xlsx": ONS + "yearendingjune2025/ltimnov25.xlsx",
    "ho_visas_summary.ods": "https://assets.publishing.service.gov.uk/media/6a85c6003d82f78d5c514552/visas-summary-jun-2026-tables.ods",
    "ho_asylum_summary.ods": "https://assets.publishing.service.gov.uk/media/6a85c315b0504df9f2c89800/asylum-summary-jun-2026-tables.ods",
    "ho_illegal_entry_summary.ods": "https://assets.publishing.service.gov.uk/media/6a8c11c3a8f84a582b84281a/illegal-entry-routes-to-the-uk-summary-jun-2026-tables.ods",
}
T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TX = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFF = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
report: list[str] = []


def ods_rows(path, max_rows=22):
    root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
    for table in root.iter(T + "table"):
        rows = []
        for r in table.iter(T + "table-row"):
            vals = []
            for c in r.findall(T + "table-cell"):
                rep = min(int(c.get(T + "number-columns-repeated", "1")), 30)
                v = c.get(OFF + "value") or "".join(p.text or "" for p in c.iter(TX + "p"))
                vals.extend([v] * rep)
            if any(vals):
                rows.append(vals)
            if len(rows) >= max_rows:
                break
        yield table.get(T + "name"), rows


for name, url in TARGETS.items():
    p = OUT / name
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            p.write_bytes(r.read())
    except Exception as exc:  # noqa: BLE001
        report.append(f"\n# {name}: FETCH FAILED {exc}")
        continue
    report.append(f"\n# {name} ({p.stat().st_size:,} bytes) {url}")
    if p.suffix == ".xlsx":
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        for ws in wb.worksheets:
            report.append(f"\n## sheet `{ws.title}`")
            n = 0
            for row in ws.iter_rows(values_only=True):
                cells = [str(c)[:50] for c in row if c is not None]
                if cells:
                    report.append(" | ".join(cells[:16]))
                    n += 1
                if n >= 22:
                    break
    else:
        for sheet, rows in ods_rows(p):
            report.append(f"\n## sheet `{sheet}`")
            for vals in rows:
                report.append(" | ".join(v[:50] for v in vals if v)[:600])

(OUT / "REPORT.md").write_text("\n".join(report) + "\n")
