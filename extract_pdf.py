import re
import pymupdf  

def parse_bca(pdf_file):
    transactions = []

    date_pattern = re.compile(r"^(\d{2}/\d{2})\s+(.*)")
    amount_pattern = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b|\b\d+\.\d{2}\b")

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

    # Open uploaded PDF directly from memory
    pdf_bytes = pdf_file.read()

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text("text", sort=True)
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

                # Skip page numbers (e.g., "1 / 2" or "2 / 2")
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
        raw_full_text = "\n".join([remaining_text] + block[1:])

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
        keterangan = keterangan.replace("\r", " ").replace("\n", " ")

        # 2. Remove numeric amounts
        for amt in raw_amounts:
            keterangan = keterangan.replace(amt, "")

        # 3. Apply pattern cleanup rules
        keterangan = re.sub(r"\bTRSF E-BANKING\b", "", keterangan)
        keterangan = re.sub(r"\bBYR VIA E-BANKING\b", "", keterangan)
        keterangan = re.sub(r"\bBI-FAST\b", "", keterangan)
        keterangan = re.sub(r"\S*/FTSCY/\S*", "", keterangan)
        keterangan = re.sub(r"\S*/FTFVA/\S*", "", keterangan)
        keterangan = re.sub(r"\bDB\b", "", keterangan)

        # 4. Trim spaces
        keterangan = re.sub(r"\s+", " ", keterangan).strip()

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
    


def parse_mandiri(pdf_file):
    transactions = []
    
    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }

    # Matches numbers formatted like 0.00 up to DECIMAL(12,2)
    money_pattern = re.compile(r"^\d{1,3}(,\d{3})*\.\d{2}$")

    pdf_file.seek(0)
    
    pdf_bytes = pdf_file.read()

    pdf = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )
    
    try:
    # with pdfplumber.open(pdf_path) as pdf:
        for page in pdf:
            # ----------------------------------------
            # EXTRACT WORDS USING PYMUPDF
            # ----------------------------------------
            raw_words = page.get_text("words")

            # PyMuPDF format:
            # (x0, y0, x1, y1, text, block_no, line_no, word_no)
            #
            # Convert it to the same structure that the
            # original pdfplumber code was using.
            words = []

            for w in raw_words:
                x0, y0, x1, y1, text, block_no, line_no, word_no = w

                words.append(
                    {
                        "x0": x0,
                        "x1": x1,
                        "top": y0,
                        "bottom": y1,
                        "text": text,
                    }
                )

            # Sort in reading order
            words.sort(
                key=lambda w: (w["top"], w["x0"])
            )

            # ----------------------------------------
            # FIND TRANSACTION STARTS
            # ----------------------------------------
            starts = []
            for i, word in enumerate(words):
                if (
                    word["x0"] < 120
                    and word["top"] > 80
                    and re.fullmatch(r"\d{2}", word["text"])
                ):
                    if (
                        i + 2 < len(words)
                        and words[i + 1]["text"] in month_map
                        and re.fullmatch(r"\d{4},", words[i + 2]["text"])
                    ):
                        starts.append(
                            (
                                i,
                                word["top"],
                                word["text"],
                                words[i + 1]["text"],
                                words[i + 2]["text"],
                            )
                        )

            # ----------------------------------------
            # PROCESS EACH TRANSACTION
            # ----------------------------------------
            for n, (_, top, day, month, year) in enumerate(starts):
                if n + 1 < len(starts):
                    end_top = starts[n + 1][1]
                else:
                    end_top = float("inf")

                block = [
                    w
                    for w in words
                    if top - 1 <= w["top"] < end_top - 1
                ]

                debet = 0.0
                kredit = 0.0

                # ----------------------------------------
                # READ DEBIT / CREDIT (USING RIGHT-ALIGNMENT x1)
                # ----------------------------------------
                for w in block:
                    text = w["text"]

                    if not money_pattern.fullmatch(text):
                        continue

                    value = float(text.replace(",", ""))
                    x1 = w["x1"]  # Using right edge for alignment check

                    # Physical 1st amount column (KREDIT) has right-edge x1 < 445
                    if x1 < 445:
                        kredit = value

                    # Physical 2nd amount column (DEBET) has right-edge 445 <= x1 < 515
                    elif 445 <= x1 < 515:
                        debet = value

                # ----------------------------------------
                # READ REMARK / REFERENCE
                # ----------------------------------------
                remark_words = []
                for w in block:
                    # Keep remark cutoff strictly before x=300
                    if 115 <= w["x0"] < 300:
                        if money_pattern.fullmatch(w["text"]):
                            continue
                        if w["text"] == "|":
                            continue
                        remark_words.append(w)

                remark_words.sort(key=lambda w: (w["top"], w["x0"]))

                keterangan = " ".join(w["text"] for w in remark_words)

                # --- REMARK CLEANING PIPELINE ---
                # Remove MCM Inhouse Trf / MCM InhouseTrf variants
                keterangan = re.sub(
                    r"\bMCM\s+Inhouse\s*Trf\b",
                    "",
                    keterangan,
                    flags=re.IGNORECASE,
                )

                # Cleanup whitespace and hyphens
                keterangan = re.sub(r"\s+", " ", keterangan).strip()
                keterangan = re.sub(r"(^|\s)-(?=\s|$)", " ", keterangan)
                keterangan = re.sub(r"\s+", " ", keterangan).strip()

                # Truncate to maximum 100 characters
                keterangan = keterangan[:100]

                # ----------------------------------------
                # DATE FORMAT (YYYY/MM/DD)
                # ----------------------------------------
                tanggal = f"{year[:4]}/{month_map[month]}/{day}"

                transactions.append(
                    {
                        "tanggal": tanggal,
                        "keterangan": keterangan,
                        "debit": debet,
                        "kredit": kredit,
                    }
                )
        return transactions
    except Exception:
        raise
    
    
def parse_uob(pdf_file):
    transactions = []
    
    # Matches numbers formatted like 0, 7,531, or 32,731,880 (optional decimal support added)
    money_pattern = re.compile(r"^\d{1,3}(,\d{3})*(\.\d{2})?$")

    pdf_file.seek(0)
        
    pdf_bytes = pdf_file.read()

    pdf = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )
    
    try:
    # with pdfplumber.open(pdf_path) as pdf:
        for page in pdf:
            # ----------------------------------------
            # EXTRACT WORDS USING PYMUPDF
            # ----------------------------------------
            raw_words = page.get_text("words")

            # PyMuPDF:
            # (x0, y0, x1, y1, text,
            #  block_no, line_no, word_no)
            words = []

            for w in raw_words:
                x0, y0, x1, y1, text, block_no, line_no, word_no = w

                words.append(
                    {
                        "x0": x0,
                        "x1": x1,
                        "top": y0,
                        "bottom": y1,
                        "text": text,
                    }
                )

            # Sort in reading order
            words.sort(
                key=lambda w: (w["top"], w["x0"])
            )

            # ----------------------------------------
            # FIND TRANSACTION STARTS
            # ----------------------------------------
            starts = []
            for i, word in enumerate(words):
                # Statement Date is located on the far left column (DD/MM/YYYY)
                if (
                    word["x0"] < 100
                    and word["top"] > 150
                    and re.fullmatch(r"\d{2}/\d{2}/\d{4}", word["text"])
                ):
                    starts.append((i, word["top"], word["text"]))

            # ----------------------------------------
            # PROCESS EACH TRANSACTION
            # ----------------------------------------
            for n, (_, top, date_str) in enumerate(starts):
                if n + 1 < len(starts):
                    end_top = starts[n + 1][1]
                else:
                    end_top = float("inf")

                block = [
                    w
                    for w in words
                    if top - 1 <= w["top"] < end_top - 1
                ]

                debet = 0.0
                kredit = 0.0

                # ----------------------------------------
                # READ WITHDRAWAL (DEBET) & DEPOSIT (KREDIT)
                # ADJUSTED: Column bounds swapped to align with UOB layout
                # ----------------------------------------
                for w in block:
                    text = w["text"]

                    if not money_pattern.fullmatch(text):
                        continue

                    value = float(text.replace(",", ""))
                    x0 = w["x0"]

                    # Withdrawal (IDR) / Debet
                    if 330 <= x0 < 410:
                        debet = value

                    # Deposit (IDR) / Kredit
                    elif 410 <= x0 < 480:
                        kredit = value

                # ----------------------------------------
                # READ REMARK / DESCRIPTION
                # ----------------------------------------
                remark_words = []
                for w in block:
                    if 180 <= w["x0"] < 330:
                        if money_pattern.fullmatch(w["text"]):
                            continue
                        if w["text"] in ("|", "PM", "AM"):
                            continue
                        remark_words.append(w)

                remark_words.sort(key=lambda w: (w["top"], w["x0"]))
                keterangan = " ".join(w["text"] for w in remark_words)

                # Skip header, balance summary, or footer blocks
                if any(
                    k in keterangan
                    for k in (
                        "Description",
                        "Total Deposits",
                        "Total Withdrawals",
                        "Ending Balance",
                        "Page",
                    )
                ):
                    continue

                # Clean whitespace
                keterangan = re.sub(r"\s+", " ", keterangan).strip()
                keterangan = re.sub(r"(^|\s)-(?=\s|$)", " ", keterangan)
                keterangan = re.sub(r"\s+", " ", keterangan).strip()

                # Truncate to maximum 100 characters
                keterangan = keterangan[:100]

                # FIX 2: Skip invalid entries where both debet and kredit are 0
                # (Handles footer dates or non-transaction matches)
                if debet == 0.0 and kredit == 0.0:
                    continue

                # ----------------------------------------
                # DATE FORMAT (YYYY/MM/DD)
                # ----------------------------------------
                day, month, year = date_str.split("/")
                tanggal = f"{year}/{month}/{day}"

                transactions.append(
                    {
                        "tanggal": tanggal,
                        "keterangan": keterangan,
                        "debit": debet,
                        "kredit": kredit,
                    }
                )
        return transactions
    except Exception:
        raise