import re
import pandas as pd
import pdfplumber


def parse_mufg_statement(pdf_path):
    transactions = []

    # Pattern for MUFG transaction dates e.g. "09DEC25" or "15DEC25"
    date_pattern = re.compile(r"^(\d{2}[A-Z]{3}\d{2})")

    # Regex pattern to match currency numbers (e.g., 70,000,000.00 or 10,778,593.22)
    amount_pattern = re.compile(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b")

    ignore_starts = (
        "STATEMENT",
        "OF ACCOUNT",
        "AMBICO",
        "MUFG",
        "JAKARTA BRANCH",
        "SURABAYA SUB-BRANCH",
        "STATEMENT PERIOD",
        "ACCOUNT TYPE",
        "CURRENT ACCOUNT",
        "ACCOUNT NO",
        "ACCOUNT REMARKS",
        "PAGE",
        "THIS YEAR",
        "DATE",
        "Date",
        "Value",
        "Bank Reference",
        "Check",
        "Debit Amount",
        "Credit Amount",
        "Ledger Balance",
        "Unless we receive",
        "of Account is available",
        "the Bank shall have",
        "relevant Statement",
        "Account is true",
        "OLD BALANCE",
        "DEBIT TOTAL",
        "CREDIT TOTAL",
        "NEW BALANCE",
        "A member of MUFG",
        "CONTINUED ON NEXT PAGE",
        "END OF STATEMENT",
        "(1-B)",
        "(11199345)",
    )

    all_page_blocks = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")
            page_clean_lines = []

            for line in lines:
                line_str = line.strip()

                # Filter out header, footer, and metadata lines
                if not line_str or line_str.startswith(ignore_starts):
                    continue

                if re.match(r"^\d+\s*-\s*[A-Z]{3}\s*-\s*\d+$", line_str):
                    continue

                page_clean_lines.append(line_str)

            # Group lines into transaction blocks starting with a date pattern
            page_blocks = []
            current_block = []

            for line in page_clean_lines:
                if date_pattern.match(line):
                    if current_block:
                        page_blocks.append(current_block)
                    current_block = [line]
                else:
                    if current_block:
                        current_block.append(line)

            if current_block:
                page_blocks.append(current_block)

            all_page_blocks.extend(page_blocks)

    for block in all_page_blocks:
        first_line = block[0]
        match = date_pattern.match(first_line)
        if not match:
            continue

        trx_date_raw = match.group(1)
        full_text = " ".join(block)

        # Parse amounts from block
        raw_amounts = amount_pattern.findall(full_text)
        valid_amounts = [
            float(amt.replace(",", "")) for amt in raw_amounts
        ]

        if not valid_amounts:
            continue

        raw_debet = 0.0
        raw_kredit = 0.0

        # MUFG structure check:
        # Credit entries (incoming) usually have fewer numeric values per block line,
        # or contain incoming transfer keywords (BLI-TRF, SKN-PT, CENAIDJA, NISPIDJA)
        is_incoming = any(
            kw in full_text for kw in ["CENAIDJA", "NISPIDJA", "SKN-PT", "0588539227300801"]
        )

        if is_incoming:
            raw_kredit = valid_amounts[0]
        else:
            raw_debet = valid_amounts[0]

        # Clean description (Remarks)
        keterangan = full_text
        keterangan = re.sub(r"\b\d{2}[A-Z]{3}\d{2}\b", "", keterangan)
        for amt in raw_amounts:
            keterangan = keterangan.replace(amt, "")

        keterangan = re.sub(r"\s+", " ", keterangan).strip()[:100]

        # Convert date "09DEC25" -> "2025/12/09"
        parsed_date = pd.to_datetime(trx_date_raw, format="%d%b%y").strftime(
            "%Y/%m/%d"
        )

        # Swapped assignment: raw_kredit assigned to debet, raw_debet assigned to kredit
        transactions.append(
            {
                "tanggal": parsed_date,
                "keterangan": keterangan,
                "debet": raw_kredit,
                "kredit": raw_debet,
            }
        )

    return transactions


# Execute extraction
pdf_filename = "rkmufg.pdf"
excel_filename = "rkmufg.xlsx"

data = parse_mufg_statement(pdf_filename)
df = pd.DataFrame(data)

df.to_excel(excel_filename, index=False)
print(f"Selesai! Total transaksi: {len(data)}")
print(df)
