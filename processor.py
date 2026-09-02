import extract_csv 
import extract_pdf

PROCESSORS = {
    "BCA":{
        "text/csv":extract_csv.parse_bca,
        "application/pdf":extract_pdf.parse_bca,  
    },
    "UOB":{
        # "text/csv":extract_csv.parse_uob,
        "application/pdf":extract_pdf.parse_uob,  
    },
    "MASPION":{
        # "text/csv":extract_csv.parse_maspion,
        # "application/pdf":extract_pdf.parse_maspion,  
    },
    "MANDIRI":{
        # "text/csv":extract_csv.parse_mandiri,
        "application/pdf":extract_pdf.parse_mandiri,  
    },
    "MUFG":{
        # "text/csv":extract_csv.parse_mandiri,
        "application/pdf":extract_pdf.parse_mufg,  
    },
    "OCBC - NISP":{
        # "text/csv":extract_csv.parse_mandiri,
        "application/pdf":extract_pdf.parse_ocbc,  
    },
}

def process(bank_origin,file_type,file):
    bank_processors = PROCESSORS.get(bank_origin)

    if bank_processors is None:
        raise ValueError(f"😢 Oops! Konversi dari bank {bank_origin} belum tersedia")
    
    processor = bank_processors.get(file_type)

    if processor is None:
        file_type = file_type.rsplit("/", 1)[1]
        raise ValueError(
            f"😵‍💫 Uh oh! Konversi '{file_type}' untuk bank '{bank_origin}' belum tersedia"
        )

    return processor(file)
