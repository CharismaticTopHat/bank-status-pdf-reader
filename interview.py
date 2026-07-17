import re
import csv
import pdfplumber
from collections import defaultdict

PDF_FILE = "./ESTADO DE CUENTA.pdf"
CSV_FILE = "output.csv"

# Columns for the CSV
OUTPUT_COLUMNS = [
    "OPER", "LIQ", "COD.", "DESCRIPCION", "REFERENCIA",
    "CARGOS", "ABONOS", "OPERACION", "LIQUIDACION",
]

# Max possible headers
RANGE_HEADERS = ["OPER", "LIQ", "COD.", "DESCRIPCION", "REFERENCIA", "CARGOS", "ABONOS", "OPERACION", "LIQUIDACION"]
# Always present on each cell
ANCHOR_HEADERS = {"OPER", "LIQ", "COD.", "DESCRIPCION"}

# Regular expressions to gather OPER and REFERENCIA contents from text, rather than coordinates
REF_PATTERN = re.compile(r"^ref\.?$", re.IGNORECASE)
DATE_PATTERN = re.compile(r"^\d{2}/[A-Z]{3}$", re.IGNORECASE)

ROW_Y_TOLERANCE = 3
HEADER_ROW_TOLERANCE = 2
FOOTER_MARKERS = {"Estimado", "Total", "INSTITUCION"}

def extract_words(page):
    return page.extract_words(
        x_tolerance=1, y_tolerance=1,
        keep_blank_chars=False, use_text_flow=False,
    )

def find_header_row(words):
    """
    Locate the header row with Anocher Headers(OPER+LIQ+COD.+DESCRIPCION.
    """
    all_names = RANGE_HEADERS
    candidates = defaultdict(list)
    for w in words:
        t = w["text"].upper().rstrip(":")
        if t in all_names:
            candidates[t].append(w)

    rows = defaultdict(dict)
    for name, ws in candidates.items():
        for w in ws:
            top = w["top"]
            bucket_key = None
            for key in rows:
                if abs(key - top) <= HEADER_ROW_TOLERANCE:
                    bucket_key = key
                    break
            if bucket_key is None:
                bucket_key = top
            rows[bucket_key][name] = w

    best_row, best_count = None, -1
    for top, found in rows.items():
        if ANCHOR_HEADERS.issubset(found.keys()) and len(found) > best_count:
            best_count = len(found)
            best_row = found

    if best_row is None:
        return {name: None for name in all_names}
    return {name: best_row.get(name) for name in all_names}


def build_column_ranges(headers):
    """
    Identify midpoint for the data which doesn't necessarily start at the same x-position as its header label.
    """
    found = sorted(
        ((k, v["x0"]) for k, v in headers.items() if v is not None),
        key=lambda item: item[1],
    )
    ranges = []
    for i, (name, x0) in enumerate(found):
        left = float("-inf") if i == 0 else (found[i - 1][1] + x0) / 2
        right = float("inf") if i == len(found) - 1 else (x0 + found[i + 1][1]) / 2
        ranges.append((name, left, right))
    return ranges


def col_for_x(x, ranges):
    for name, left, right in ranges:
        if left < x <= right:
            return name
    return None


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


def get_canonical_ranges(pdf):
    """
    Use the page with the most complete header set to establish column boundaries, reused for every page even if later pages miss some header
    """
    best_headers, best_count = None, -1
    for page in pdf.pages:
        words = extract_words(page)
        headers = find_header_row(words)
        count = sum(1 for v in headers.values() if v is not None)
        if count > best_count:
            best_count = count
            best_headers = headers
    return build_column_ranges(best_headers)

def process_page(page, canonical_ranges):
    words = extract_words(page)
    headers = find_header_row(words)

    if not any(headers.values()):
        return []  # No transactions table on this page

    header_bottom = max(h["bottom"] for h in headers.values() if h is not None)

    footer_top = float("inf")
    for w in words:
        if w["top"] > header_bottom and w["text"] in FOOTER_MARKERS:
            footer_top = min(footer_top, w["top"])

    body_words = [w for w in words if header_bottom < w["top"] < footer_top]
    rows = cluster_rows(body_words)

    records = []
    for row in rows:
        row_sorted = sorted(row, key=lambda w: w["x0"])
        record = {c: [] for c in RANGE_HEADERS}
        for w in row_sorted:
            col = col_for_x(w["x0"], canonical_ranges)
            if col:
                record[col].append(w["text"])

        line = {c: " ".join(record[c]).strip() for c in RANGE_HEADERS}
        
        # Wrapped continuation row  for DESCRIPCION and REFERENCIA (no OPER date) whose text starts with
        # "Ref." is REFERENCIA; otherwise everything is DESCRIPCION.
        zone_text = " ".join(filter(None, [line["DESCRIPCION"], line["REFERENCIA"]])).strip()
        line["DESCRIPCION"] = zone_text
        line["REFERENCIA"] = ""

        if not DATE_PATTERN.match(line["OPER"]) and zone_text:
            zone_words = zone_text.split()
            if zone_words and REF_PATTERN.match(zone_words[0]):
                line["REFERENCIA"] = zone_text
                line["DESCRIPCION"] = ""

        records.append({c: line.get(c, "") for c in OUTPUT_COLUMNS})

    return records


def is_continuation(line):
    return not DATE_PATTERN.match(line["OPER"])


def main():
    all_records = []
    with pdfplumber.open(PDF_FILE) as pdf:
        canonical_ranges = get_canonical_ranges(pdf)
        for page in pdf.pages:
            for line in process_page(page, canonical_ranges):
                if not any(line.values()):
                    continue
                if is_continuation(line) and all_records:
                    prev = all_records[-1]
                    extra_desc = " ".join(
                        filter(None, [line["OPER"], line["LIQ"], line["COD."], line["DESCRIPCION"]])
                    ).strip()
                    if extra_desc:
                        prev["DESCRIPCION"] = (prev["DESCRIPCION"] + " " + extra_desc).strip()
                    if line["REFERENCIA"]:
                        prev["REFERENCIA"] = (prev["REFERENCIA"] + " " + line["REFERENCIA"]).strip()
                else:
                    all_records.append(line)

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"Saved {len(all_records)} rows to {CSV_FILE}")


if __name__ == "__main__":
    main()