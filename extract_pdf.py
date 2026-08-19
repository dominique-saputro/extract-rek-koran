import re
import pandas as pd
import pymupdf  


def parse_bca(pdf_file):
    transactions = []

    date_pattern = re.compile(r"^(\d{2}/\d{2})\s+(.*)")
    amount_pattern = re.compile(
        r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b|\b\d+\.\d{2}\b"
    )

    ignore_starts = (
        "SALDO AKHIR",
        "MUTASI CR",
        "MUTASI DB",
        "PERIODE",
        "NO. REKENING",
        "HALAMAN",
        "TANGGAL KETERANGAN",
        "Bersambung ke",
        "CATATAN:",
        "•",
        "REKENING GIRO",
        "KCU",
        "MATA UANG",
    )

    year = None
    all_page_blocks = []
    
    pdf_file.seek(0)

    pdf_bytes = pdf_file.read()

    pdf = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    # Open PDF using PyMuPDF
    # with pymupdf.open(pdf_file) as pdf:
    try:
        for page in pdf:
            # Extract text using PyMuPDF
            text = page.get_text("text")

            if not text:
                continue

            lines = text.splitlines()

            # Extract year from header 'PERIODE : MARET 2026'
            if not year:
                for line in lines:
                    if "PERIODE" in line:
                        periode_match = re.search(
                            r"PERIODE\s*:\s*([A-Za-z]+)\s+(\d{4})",
                            line,
                            re.IGNORECASE,
                        )

                        if periode_match:
                            _, year_str = periode_match.groups()
                            year = year_str
                            break

            # Clean header and footer lines for THIS PAGE ONLY
            page_clean_lines = []

            for line in lines:
                line_str = line.strip()

                if not line_str or line_str.startswith(ignore_starts):
                    continue

                # Skip page numbers (e.g. "1 / 2" or "2 / 2")
                if re.match(r"^\d+\s*/\s*\d+$", line_str):
                    continue

                page_clean_lines.append(line_str)

            # Group lines into transaction blocks FOR THIS PAGE ONLY
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

        if not year:
            year = "2026"

        # Process all transaction blocks across pages
        for block in all_page_blocks:
            first_line = block[0]

            match = date_pattern.match(first_line)

            if not match:
                continue

            dd_mm, remaining_text = match.groups()

            # Join block lines with newlines
            raw_full_text = "\n".join(
                [remaining_text] + block[1:]
            )

            # Skip SALDO AWAL entry
            if "SALDO AWAL" in raw_full_text:
                continue

            # Format date as YYYY/MM/DD
            day, mon = dd_mm.split("/")

            tanggal_formatted = f"{year}/{mon}/{day}"

            # Extract numeric amounts
            raw_amounts = amount_pattern.findall(raw_full_text)

            valid_amounts = []

            for a in raw_amounts:
                clean_a = a.replace(",", "")

                if len(clean_a) >= 4 or "." in clean_a:
                    valid_amounts.append(clean_a)

            # Check DB flag
            has_db = (
                " DB" in raw_full_text
                or "DB " in raw_full_text
                or raw_full_text.strip().endswith("DB")
            )

            debet = 0.0
            kredit = 0.0

            if valid_amounts:
                mutasi_val = float(valid_amounts[0])

                if has_db:
                    kredit = mutasi_val
                else:
                    debet = mutasi_val

            # --- REMARK CLEANING PIPELINE ---
            keterangan = raw_full_text

            # 1. Remove newlines / enter characters
            keterangan = (
                keterangan
                .replace("\r", " ")
                .replace("\n", " ")
            )

            # 2. Remove numeric amounts
            for amt in raw_amounts:
                keterangan = keterangan.replace(amt, "")

            # 3. Apply pattern cleanup rules
            keterangan = re.sub(
                r"\bTRSF E-BANKING\b",
                "",
                keterangan,
            )

            keterangan = re.sub(
                r"\bBYR VIA E-BANKING\b",
                "",
                keterangan,
            )

            keterangan = re.sub(
                r"\bBI-FAST\b",
                "",
                keterangan,
            )

            keterangan = re.sub(
                r"\S*/FTSCY/\S*",
                "",
                keterangan,
            )

            keterangan = re.sub(
                r"\S*/FTFVA/\S*",
                "",
                keterangan,
            )

            keterangan = re.sub(
                r"\bDB\b",
                "",
                keterangan,
            )

            # 4. Trim spaces
            keterangan = re.sub(
                r"\s+",
                " ",
                keterangan,
            ).strip()

            # 5. Take first 100 characters from the LEFT
            keterangan = keterangan[:100]

            transactions.append(
                {
                    "tanggal": tanggal_formatted,
                    "keterangan": keterangan,
                    "debet": debet,
                    "kredit": kredit,
                }
            )
        return transactions
    except Exception as e:
        return e

