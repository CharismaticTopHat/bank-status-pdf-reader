# Campos a extraer: 
"""
a. FECHA OPERACIÓN
b. FECHA LIQUIDACIÓN
c. COD. DESCRIPCIÓN
d. REFERENCIA
e. CARGOS
f. ABONOS
g. SALDO OPERACIÓN
h. SALDO LIQUIDACIÖN
"""

import pdfplumber
from pdfplumber.utils.pdfinternals import resolve_and_decode, resolve

from collections import defaultdict

pdf = pdfplumber.open("./ESTADO DE CUENTA.pdf")

headers = {
    "OPER": None,
    "LIQ": None,
    "COD.": None,
    "DESCRIPCION": None,
    "REFERENCIA": None,
    "CARGOS": None,
    "ABONOS": None,
    "OPERACION": None,
    "LIQUIDACION": None
}

#for page in pdf.pages:
words = pdf.pages[0].extract_words(
    x_tolerance=1,
    y_tolerance=1,
    keep_blank_chars=False
)

for word in words:
    text = word["text"].upper()

    if text in headers:
        headers[text] = word

print(headers)

columns = {
    name: info["x0"]
    for name, info in headers.items()
    if info is not None
}

columns = dict(sorted(columns.items(), key=lambda x: x[1]))

print(columns)

header_bottom = max(
    info["bottom"]
    for info in headers.values()
    if info is not None
)

column_names = list(columns.keys())
column_x = list(columns.values())

for word in words:

    if word["top"] <= header_bottom:
        continue

    x = word["x0"]

    for i in range(len(column_x)-1, -1, -1):
        if x >= column_x[i]:
            print(f"{column_names[i]:15} -> {word['text']}")
            break