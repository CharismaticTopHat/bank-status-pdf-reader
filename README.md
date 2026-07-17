# Installation

1. Open a terminal.
2. Navigate to the project directory.
3. Install the required dependencies by running:

```bash
pip install -r requirements.txt
```

# Execution

1. Place the bank statement PDF you want to process inside the project folder (or any accessible location).
2. Open `interview.py`.
3. Update the `PDF_FILE` variable with the path to the PDF you want to analyze. For example:

```python
PDF_FILE = "ESTADO DE CUENTA.pdf"
```

or

```python
PDF_FILE = "path/to/your/file.pdf"
```

4. Run the script:

```bash
python interview.py
```

5. Once the execution finishes, the extracted data will be saved as `output.csv` in the project directory.

## Identified characteristics of the problem
- .extract_table() doesn't work to extract the data, so it's not usable.
- We want to collect the data  from the rows OPER, LIQ, COD., DESCRIPCION, REFERENCIA, CARGOS, ABONOS, OPERACION, LIQUIDACION.
- Each line ALWAYS has OPER, LIQ, COD. and DESCRIPCION, but the remaining rows can be empty (REFERENCIA, CARGOS, ABONOS, OPERACION, LIQUIDACION).
- The coordinates for REFERENCIA are tricky since the content is usually below the coordinates of DESCRIPCION. However, it always starts with "Ref.".
- The coordinates for OPER are tricky since the content doesn't start at the same x0 as the header.
- Multiple pages through the whole PDF are analyzed to gather all the data we want.
- Pages 2 and 3 are missing the header REFERENCIA, so header coordinates aren't required to get this row specifically.
- The function .extract_words() is the one used to get coordinates to gather the data.
- Coordinates aren't an absolute response to gather all the wanted data (such with REFERENCIA and OPER).