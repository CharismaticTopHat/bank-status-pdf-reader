"""
Extract transaction rows from a bank-statement PDF using pdfplumber,
based on word-position (x0) column mapping rather than page.extract_table().

Columns collected:
OPER | LIQ | COD. | DESCRIPCION | REFERENCIA | CARGOS | BONOS | OPERACION | LIQUIDACION

Special handling:
- REFERENCIA always starts with a token "Ref." (case-insensitive), even when
  it visually falls under the DESCRIPCION column. That token, and everything
  after it up to the start of the CARGOS column, is forced into REFERENCIA.
- Continuation lines (OPER/LIQ/COD. empty, just a wrapped "Ref. ..." line)
  are merged into the previous transaction row instead of creating a new one.
"""

import re
import csv
import pdfplumber

# ------------------------------------------------------------------ #
# Configuration
# ------------------------------------------------------------------ #
PDF_FILE = "./ESTADO DE CUENTA.pdf"      # <-- update with your PDF path
CSV_FILE = "output.csv"

COLUMNS = [
    "OPER", "LIQ", "COD.", "DESCRIPCION", "REFERENCIA",
    "CARGOS", "BONOS", "OPERACION", "LIQUIDACION",
]

REF_PATTERN = re.compile(r"^ref\.?$", re.IGNORECASE)

ROW_Y_TOLERANCE = 3   # px tolerance to consider two words on the same row
FOOTER_MARKER = "Estimado"  # word that marks the end of the table on a page


# ------------------------------------------------------------------ #
# Header detection (per page, since headers repeat on every page)
# ------------------------------------------------------------------ #
def extract_words(page):
    return page.extract_words(
        x_tolerance=1, y_tolerance=1,
        keep_blank_chars=False, use_text_flow=False,
    )


def find_headers(words):
    headers = {name: None for name in COLUMNS}
    for w in words:
        text = w["text"].upper().rstrip(":")
        if text in headers and headers[text] is None:
            headers[text] = w
    return headers


def build_column_ranges(headers):
    found = sorted(
        ((k, v["x0"]) for k, v in headers.items() if v is not None),
        key=lambda item: item[1],
    )
    ranges = []
    for i, (name, left) in enumerate(found):
        right = found[i + 1][1] if i < len(found) - 1 else float("inf")
        ranges.append((name, left, right))
    return ranges


def col_for_x(x, ranges):
    for name, left, right in ranges:
        if left <= x < right:
            return name
    return None


# ------------------------------------------------------------------ #
# Row grouping
# ------------------------------------------------------------------ #
def cluster_rows(words, y_tol=ROW_Y_TOLERANCE):
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        placed = False
        for row in rows:
            if abs(row[0]["top"] - w["top"]) <= y_tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    rows.sort(key=lambda r: r[0]["top"])
    return rows


# ------------------------------------------------------------------ #
# Per-page processing
# ------------------------------------------------------------------ #
def process_page(page):
    words = extract_words(page)
    headers = find_headers(words)

    if not any(headers.values()):
        return []  # this page has no matching table (e.g. cover page)

    ranges = build_column_ranges(headers)
    header_bottom = max(h["bottom"] for h in headers.values() if h is not None)

    footer_top = float("inf")
    for w in words:
        if w["text"] == FOOTER_MARKER:
            footer_top = w["top"]
            break

    body_words = [w for w in words if header_bottom < w["top"] < footer_top]
    rows = cluster_rows(body_words)

    cargos_left = next((left for name, left, _ in ranges if name == "CARGOS"), float("inf"))

    records = []
    for row in rows:
        row_sorted = sorted(row, key=lambda w: w["x0"])
        record = {c: [] for c in COLUMNS}

        ref_idx = None
        for i, w in enumerate(row_sorted):
            if REF_PATTERN.match(w["text"]):
                ref_idx = i
                break

        if ref_idx is not None:
            # words before "Ref." keep their normal column assignment
            for w in row_sorted[:ref_idx]:
                col = col_for_x(w["x0"], ranges)
                if col:
                    record[col].append(w["text"])
            # from "Ref." onward: force into REFERENCIA unless it's past
            # the start of the numeric columns (CARGOS/BONOS/etc.)
            for w in row_sorted[ref_idx:]:
                if w["x0"] >= cargos_left:
                    col = col_for_x(w["x0"], ranges)
                    if col:
                        record[col].append(w["text"])
                else:
                    record["REFERENCIA"].append(w["text"])
        else:
            for w in row_sorted:
                col = col_for_x(w["x0"], ranges)
                if col:
                    record[col].append(w["text"])

        line = {c: " ".join(record[c]).strip() for c in COLUMNS}
        records.append(line)

    return records


def is_continuation(line):
    return not line["OPER"] and not line["LIQ"] and not line["COD."]


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #
def main():
    all_records = []

    with pdfplumber.open(PDF_FILE) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for line in process_page(page):
                if not any(line.values()):
                    continue  # skip fully blank rows
                if is_continuation(line) and all_records:
                    prev = all_records[-1]
                    for c in ("DESCRIPCION", "REFERENCIA"):
                        if line[c]:
                            prev[c] = (prev[c] + " " + line[c]).strip()
                else:
                    all_records.append(line)

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"Saved {len(all_records)} rows to {CSV_FILE}")


if __name__ == "__main__":
    main()