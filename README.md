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