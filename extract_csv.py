import csv
import re
import pandas as pd


def parse_bca(csv_file):
    transactions = []

    # Regex pattern to match amounts in text
    amount_pattern = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b|\b\d+\.\d{2}\b")

    year = "2026"  # Fallback default

    csv_file.seek(0)
    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode(
            "utf-8",
            errors="ignore",
        )
    reader = csv.reader(
        content.splitlines()
    )

    # with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
    #     reader = csv.reader(f)
    try:
        for row in reader:
            if not row:
                continue

            full_line_str = " ".join(row)

            # Extract Year from header (e.g., 'Periode : 01/07/2026 - 31/07/2026')
            if "Periode" in full_line_str and not year:
                periode_match = re.search(r"(\d{4})", full_line_str)
                if periode_match:
                    year = periode_match.group(1)

            # Identify transaction row (Column 0 matches DD/MM format)
            if len(row) >= 4 and re.match(r"^\d{2}/\d{2}$", row[0].strip()):
                dd_mm = row[0].strip()
                raw_keterangan = row[1]
                jumlah_str = row[3].strip()

                # Format date into YYYY/MM/DD
                day, mon = dd_mm.split("/")
                tanggal_formatted = f"{year}/{mon}/{day}"

                # Extract numeric value from 'Jumlah' column (e.g., '830,000.00 CR')
                match_amt = re.search(r"([\d,]+\.\d{2}|\d+)", jumlah_str)
                amt_val = 0.0
                if match_amt:
                    amt_val = float(match_amt.group(1).replace(",", ""))

                # Check DB flag
                has_db = (
                    "DB" in jumlah_str
                    or " DB" in raw_keterangan
                    or raw_keterangan.strip().startswith("DB")
                )

                debet = 0.0
                kredit = 0.0
                if has_db:
                    kredit = amt_val
                else:
                    debet = amt_val

                # --- REMARK CLEANING PIPELINE ---
                keterangan = raw_keterangan

                # 1. Remove line breaks
                keterangan = keterangan.replace("\r", " ").replace("\n", " ")

                # 2. Remove numeric amounts from description text
                raw_amounts = amount_pattern.findall(keterangan)
                for amt in raw_amounts:
                    if "." in amt or len(amt.replace(",", "")) >= 4:
                        keterangan = keterangan.replace(amt, "")

                # 3. Apply pattern cleanup rules
                keterangan = re.sub(r"\bTRSF E-BANKING\b", "", keterangan)
                keterangan = re.sub(r"\bBYR VIA E-BANKING\b", "", keterangan)
                keterangan = re.sub(r"\bBI-FAST\b", "", keterangan)
                keterangan = re.sub(
                    r"\S*/FTSCY/\S*", "", keterangan
                )  # Wildcard */FTSCY/*
                keterangan = re.sub(
                    r"\S*/FTFVA/\S*", "", keterangan
                )  # Wildcard */FTFVA/*
                keterangan = re.sub(r"\bDB\b", "", keterangan)

                # 4. Trim spaces
                keterangan = re.sub(r"\s+", " ", keterangan).strip()

                # 5. Take first 100 characters from the LEFT
                keterangan = keterangan[:100]

                transactions.append(
                    {
                        "tanggal": tanggal_formatted,
                        "keterangan": keterangan,
                        "debit": debet,
                        "kredit": kredit,
                    }
                )

        return transactions
    except Exception as e:
        return e


