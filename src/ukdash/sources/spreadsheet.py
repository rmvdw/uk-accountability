"""Read publisher spreadsheets into plain rows of strings.

ODS (OpenDocument, used by GOV.UK statistics) is read with the standard library;
XLSX with openpyxl. Both return {sheet name: [row, ...]}, where each row is a
list of cell values as strings ("" for empty), with numbers as Python reprs of
their stored values, so parsers see exactly what the publisher stored.
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

_T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TX = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_OFF = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_MAX_REPEAT = 200  # trailing empty cells/rows are stored as huge repeat counts


def _ods_cell(cell: ET.Element) -> str:
    kind = cell.get(_OFF + "value-type")
    if kind in ("float", "percentage", "currency"):
        v = cell.get(_OFF + "value", "")
        f = float(v)
        return repr(int(f)) if f.is_integer() else repr(f)
    return "\n".join("".join(p.itertext()) for p in cell.iter(_TX + "p")).strip()


def read_ods(raw: bytes) -> dict[str, list[list[str]]]:
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(raw)).read("content.xml"))
    sheets: dict[str, list[list[str]]] = {}
    for table in root.iter(_T + "table"):
        rows: list[list[str]] = []
        for r in table.iter(_T + "table-row"):
            vals: list[str] = []
            for c in r:
                if c.tag not in (_T + "table-cell", _T + "covered-table-cell"):
                    continue
                rep = min(int(c.get(_T + "number-columns-repeated", "1")), _MAX_REPEAT)
                vals.extend([_ods_cell(c)] * rep)
            while vals and vals[-1] == "":
                vals.pop()
            rep_rows = min(int(r.get(_T + "number-rows-repeated", "1")), _MAX_REPEAT)
            rows.extend([vals] * (1 if not vals else rep_rows))
        sheets[table.get(_T + "name")] = rows
    return sheets


def read_xlsx(raw: bytes) -> dict[str, list[list[str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sheets: dict[str, list[list[str]]] = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = []
            for v in row:
                if v is None:
                    vals.append("")
                elif isinstance(v, float) and v.is_integer():
                    vals.append(repr(int(v)))
                elif isinstance(v, (int, float)):
                    vals.append(repr(v))
                else:
                    vals.append(str(v).strip())
            while vals and vals[-1] == "":
                vals.pop()
            rows.append(vals)
        sheets[ws.title] = rows
    return sheets


def read_spreadsheet(raw: bytes) -> dict[str, list[list[str]]]:
    if raw[:2] != b"PK":
        raise ValueError("not a zip-based spreadsheet (expected ODS or XLSX)")
    names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
    if "content.xml" in names:
        return read_ods(raw)
    if "xl/workbook.xml" in names:
        return read_xlsx(raw)
    raise ValueError("unrecognised spreadsheet format")


def first_line(cell: str) -> str:
    """Header cells often carry note markers on later lines: 'British\\n[definition 2]'."""
    return cell.split("\n", 1)[0].strip()


def find_row(rows: list[list[str]], first_cell: str) -> int:
    """Index of the first row whose first cell (first line) equals `first_cell`."""
    for i, r in enumerate(rows):
        if r and first_line(r[0]) == first_cell:
            return i
    raise ValueError(f"no row starting with {first_cell!r}")
