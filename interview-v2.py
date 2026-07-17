import pdfplumber
import csv


PDF_FILE = "ESTADO DE CUENTA.pdf"
OUTPUT_CSV = "estado_cuenta.csv"


HEADERS = [
    "OPER",
    "LIQ",
    "COD.",
    "DESCRIPCION",
    "REFERENCIA",
    "CARGOS",
    "ABONOS",
    "OPERACION",
    "LIQUIDACION",
]


def find_headers(words):

    headers = {
        h: None
        for h in HEADERS
    }

    for word in words:

        text = word["text"].upper()

        if text in headers and headers[text] is None:
            headers[text] = word


    # Need the important headers at least
    required = [
        "OPER",
        "LIQ",
        "COD.",
        "DESCRIPCION"
    ]

    if not all(headers[h] for h in required):
        return None


    return headers



def build_column_ranges(headers):

    found = []

    for name, word in headers.items():

        if word:

            found.append(
                (
                    name,
                    word["x0"]
                )
            )


    found.sort(
        key=lambda x:x[1]
    )


    ranges=[]


    for i,(name,left) in enumerate(found):

        if i == len(found)-1:
            right=float("inf")

        else:
            right=found[i+1][1]


        ranges.append(
            (
                name,
                left,
                right
            )
        )


    return ranges



def get_column(x0, ranges):

    for name,left,right in ranges:

        if left <= x0 < right:
            return name

    return None



def find_table_limits(words, headers):


    header_bottom=max(
        w["bottom"]
        for w in headers.values()
        if w
    )


    footer_top=float("inf")


    for word in words:

        if word["text"]=="Estimado":

            footer_top=word["top"]
            break


    return header_bottom, footer_top




def group_rows(words, tolerance=3):

    rows=[]


    for word in sorted(
        words,
        key=lambda w:(w["top"],w["x0"])
    ):


        added=False


        for row in rows:

            if abs(row["top"]-word["top"]) <= tolerance:

                row["words"].append(word)
                added=True
                break


        if not added:

            rows.append(
                {
                    "top":word["top"],
                    "words":[word]
                }
            )


    return rows




def extract_reference(description):

    if "Ref." not in description:

        return description,""


    idx=description.index("Ref.")

    return (
        description[:idx].strip(),
        description[idx:].strip()
    )



def parse_row(words, ranges):


    row={
        h:""
        for h in HEADERS
    }


    for word in sorted(
        words,
        key=lambda w:w["x0"]
    ):


        col=get_column(
            word["x0"],
            ranges
        )


        if col:

            if row[col]:

                row[col]+=" "

            row[col]+=word["text"]



    #
    # Remove headers/totals/etc
    #

    required=[
        row["OPER"],
        row["LIQ"],
        row["COD."],
        row["DESCRIPCION"]
    ]


    if not all(required):

        return None



    #
    # Handle Ref. appearing inside DESCRIPTION
    #

    desc,ref=extract_reference(
        row["DESCRIPCION"]
    )


    row["DESCRIPCION"]=desc


    if ref:

        row["REFERENCIA"]=ref



    return row




def extract_statement(pdf_file):

    result=[]


    with pdfplumber.open(pdf_file) as pdf:


        for page_number,page in enumerate(pdf.pages,1):


            print(
                "Processing page",
                page_number
            )


            words=page.extract_words(
                x_tolerance=1,
                y_tolerance=1,
                keep_blank_chars=False,
                use_text_flow=False
            )


            headers=find_headers(words)


            if not headers:

                continue



            ranges=build_column_ranges(
                headers
            )


            header_bottom,footer_top=find_table_limits(
                words,
                headers
            )


            #
            # Keep only table contents
            #

            table_words=[
                w
                for w in words
                if (
                    w["top"] > header_bottom
                    and
                    w["top"] < footer_top
                )
            ]


            rows=group_rows(
                table_words
            )


            for row in rows:


                parsed=parse_row(
                    row["words"],
                    ranges
                )


                if parsed:

                    result.append(parsed)



    return result




def save_csv(data,file):

    with open(
        file,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:


        writer=csv.DictWriter(
            f,
            fieldnames=HEADERS
        )


        writer.writeheader()

        writer.writerows(data)



if __name__=="__main__":


    rows=extract_statement(
        PDF_FILE
    )


    print(
        "Rows extracted:",
        len(rows)
    )


    save_csv(
        rows,
        OUTPUT_CSV
    )