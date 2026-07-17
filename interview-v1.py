import pdfplumber
import re

PDF_FILE = "./ESTADO DE CUENTA.pdf"

headers = {
    "OPER": None,
    "LIQ": None,
    "COD.": None,
    "DESCRIPCION": None,
    "REFERENCIA": None,
    "CARGOS": None,
    "ABONOS": None,
    "OPERACION": None,
    "LIQUIDACION": None,
}

DATE_PATTERN = re.compile(r"\d{2}/[A-Z]{3}")
AMOUNT_RE = re.compile(r"^\d{1,3}(,\d{3})*\.\d{2}$")

with pdfplumber.open(PDF_FILE) as pdf:

    page = pdf.pages[1]

    words = page.extract_words(
        x_tolerance=1,
        y_tolerance=1,
        keep_blank_chars=False,
        use_text_flow=False
    )

    ###########################################################
    # Find headers
    ###########################################################

    for word in words:

        text = word["text"].upper()

        if text in headers and headers[text] is None:
            headers[text] = word

    ###########################################################
    # Build column ranges
    ###########################################################

    found = {
        k: v["x0"]
        for k, v in headers.items()
        if v is not None
    }

    found = sorted(found.items(), key=lambda x: x[1])

    column_ranges = []

    for i, (name, left) in enumerate(found):

        if i == len(found) - 1:
            right = float("inf")
        else:
            right = found[i + 1][1]

        column_ranges.append((name, left, right))

    ###########################################################
    # Header / footer limits
    ###########################################################

    header_bottom = max(
        h["bottom"]
        for h in headers.values()
        if h is not None
    )

    footer_top = float("inf")

    for word in words:
        if word["text"] == "Estimado":
            footer_top = word["top"]
            break

    ###########################################################
    # Classify every word
    ###########################################################

    classified = []

    for word in words:

        if not (header_bottom < word["top"] < footer_top):
            continue

        text = word["text"]

        if AMOUNT_RE.match(text):
            x = word["x1"]
        else:
            x = (word["x0"] + word["x1"]) / 2

        column = None

        for name, left, right in column_ranges:

            if left <= x < right:
                column = name
                break

        if column is None:
            continue

        classified.append({
            "column": column,
            "text": text,
            "top": word["top"],
            "x": x
        })

    ###########################################################
    # Sort exactly as they appear in the PDF
    ###########################################################

    classified.sort(key=lambda w: (w["top"], w["x"]))

    ###########################################################
    # Build transactions
    ###########################################################

    transactions = []

    current = None

    for item in classified:

        column = item["column"]
        text = item["text"]

        #######################################################
        # New transaction
        #######################################################

        if column == "OPER" and DATE_PATTERN.match(text):

            if current is not None:
                current["DESCRIPCION"] = " ".join(current["DESCRIPCION"]).replace(" Ref.", "")

                current["REFERENCIA"] = " ".join(current["REFERENCIA"])

                transactions.append(current)

            current = {
                "OPER": text,
                "LIQ": "",
                "COD.": "",
                "DESCRIPCION": [],
                "REFERENCIA": [],
                "CARGOS": "",
                "ABONOS": "",
                "OPERACION": "",
                "LIQUIDACION": ""
            }

            continue

        if current is None:
            continue

        #######################################################
        # Fill transaction
        #######################################################

        if column == "LIQ":

            current["LIQ"] = text

        elif column == "COD.":

            current["COD."] = text

        elif column == "DESCRIPCION":

            if text.upper() != "REF.":
                current["DESCRIPCION"].append(text)
            else:
                current["REFERENCIA"].append("Ref.")

        elif column == "REFERENCIA":

            if AMOUNT_RE.match(text):
                current["CARGOS"] = text
            else:
                current["REFERENCIA"].append(text)

        elif column == "CARGOS":

            current["CARGOS"] = text

        elif column == "ABONOS":

            current["ABONOS"] = text

        elif column == "OPERACION":

            current["OPERACION"] = text

        elif column == "LIQUIDACION":

            current["LIQUIDACION"] = text

    ###########################################################
    # Append last transaction
    ###########################################################

    if current:

        current["DESCRIPCION"] = " ".join(current["DESCRIPCION"]).replace(" Ref.", "")

        current["REFERENCIA"] = " ".join(current["REFERENCIA"])

        transactions.append(current)

    ###########################################################
    # Print
    ###########################################################

    for t in transactions:

        print("-" * 80)

        for k, v in t.items():
            print(f"{k:15}: {v}")