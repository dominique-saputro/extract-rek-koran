import re
import pandas as pd
import pdfplumber


def parse_ocbc_statement(pdf_path):
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Skip empty rows or header rows
                    if not row or not row[0]:
                        continue

                    # Match date format DD/MM/YYYY
                    date_match = re.search(r"\d{2}/\d{2}/\d{4}", row[0])
                    if not date_match:
                        continue

                    trx_date = date_match.group(0)

                    # Extract description column (Index 4 contains the main text)
                    description_raw = row[4] if len(row) > 4 and row[4] else ""
                    keterangan = re.sub(r"\s+", " ", description_raw).strip()[:100]

                    # Helper function to convert numeric strings to floats
                    def clean_amount(val_str):
                        if not val_str:
                            return 0.0
                        # Standardize dot/comma formats (e.g. 13.500,00 or 13,500.00)
                        val_str = val_str.strip().replace(" ", "")
                        if "," in val_str and "." in val_str:
                            if val_str.rfind(".") > val_str.rfind(","):
                                val_str = val_str.replace(",", "")
                            else:
                                val_str = val_str.replace(".", "").replace(",", ".")
                        elif "," in val_str:
                            val_str = val_str.replace(",", ".")
                        try:
                            return float(val_str)
                        except ValueError:
                            return 0.0

                    # Table indexes: Debit (5), Credit (6)
                    raw_debet = clean_amount(row[5] if len(row) > 5 else "")
                    raw_kredit = clean_amount(row[6] if len(row) > 6 else "")

                    # Ignore non-transaction/header balance rows
                    if raw_debet == 0.0 and raw_kredit == 0.0:
                        continue

                    # Swapped assignment: raw_kredit assigned to debet, raw_debet assigned to kredit
                    transactions.append(
                        {
                            "tanggal": pd.to_datetime(
                                trx_date, format="%d/%m/%Y"
                            ).strftime("%Y/%m/%d"),
                            "keterangan": keterangan,
                            "debet": raw_kredit,
                            "kredit": raw_debet,
                        }
                    )

    return transactions


# Execute extraction
pdf_filename = "rkocbcnisp.pdf"
excel_filename = "rkocbcnisp.xlsx"

data = parse_ocbc_statement(pdf_filename)
df = pd.DataFrame(data)

df.to_excel(excel_filename, index=False)
print(f"Selesai! Total transaksi: {len(data)}")
print(df)
