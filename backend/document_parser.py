"""
SmartStock AI — Document Ingestion and Staging Parser.
Safely extracts tabular data from CSV, Excel, PDF, and image stock sheets and invoices.
Enforces content signature validation, file size limits, SHA-256 deduplication, and zero-auto-posting staging.
"""
import csv
import hashlib
import io
import os
import re
import uuid
from datetime import datetime
from PIL import Image

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pypdf
except ImportError:
    pypdf = None

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def calculate_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_file_type(data: bytes, filename: str) -> str:
    """
    Validates file content using magic bytes and signatures rather than trusting filename extensions alone.
    """
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(f"File size {len(data)} exceeds maximum allowed limit of 10 MB")

    if data.startswith(b"%PDF-"):
        return "pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    elif data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    elif data.startswith(b"PK\x03\x04"):
        # ZIP-based container, standard for modern Office Open XML (.xlsx)
        return "xlsx"
    else:
        # Check if valid text / CSV
        try:
            sample = data[:4096].decode("utf-8")
            # If contains newlines and printable characters, treat as CSV/text
            if "\n" in sample or "\r" in sample:
                return "csv"
        except UnicodeDecodeError:
            pass

    ext = os.path.splitext(filename)[1].lower().strip(".")
    raise ValueError(f"Unsupported or unsafe file format (signature does not match allowed types: csv, xlsx, pdf, jpg, png)")


def match_ingredient(query: str, ingredients: list) -> tuple:
    """
    Matches an ingredient name from document text against active pantry items.
    Returns (ingredient_id, standard_name, confidence).
    """
    q = query.strip().lower()
    if not q:
        return (None, None, 0.0)

    # 1. Exact ID or name match
    for ing in ingredients:
        if q == ing["ingredient_id"].lower() or q == ing["name"].lower():
            return (ing["ingredient_id"], ing["name"], 1.0)

    # 2. Substring match
    for ing in ingredients:
        name_lower = ing["name"].lower()
        if q in name_lower or name_lower in q:
            return (ing["ingredient_id"], ing["name"], 0.85)

    # 3. Keyword heuristic
    keywords = {
        "chicken": "ING01", "poultry": "ING01",
        "mutton": "ING02", "goat": "ING02", "lamb": "ING02",
        "rice": "ING03", "basmati": "ING03",
        "oil": "ING04", "cooking oil": "ING04", "sunflower": "ING04",
        "onion": "ING05", "shallot": "ING05",
        "tomato": "ING06"
    }
    for kw, iid in keywords.items():
        if kw in q:
            target = [i for i in ingredients if i["ingredient_id"] == iid][0]
            return (target["ingredient_id"], target["name"], 0.75)

    return (None, query.strip(), 0.2)


def parse_csv(data: bytes, ingredients: list) -> list:
    text = data.decode("utf-8", errors="replace")
    lines = text.strip().splitlines()
    if not lines:
        return []

    # Detect delimiter
    sample = "\n".join(lines[:5])
    delim = "," if sample.count(",") >= sample.count("\t") else "\t"
    reader = csv.reader(lines, delimiter=delim)
    raw_rows = list(reader)
    if not raw_rows:
        return []

    header = [c.strip().lower() for c in raw_rows[0]]
    rows = []

    # Column index resolution
    def col_idx(*names):
        for idx, h in enumerate(header):
            for n in names:
                if n in h:
                    return idx
        return -1

    ing_col = col_idx("ingredient", "item", "product", "name")
    open_col = col_idx("opening", "start")
    rec_col = col_idx("received", "delivery", "billed_qty", "qty", "quantity")
    close_col = col_idx("closing", "end", "physical")
    supp_col = col_idx("supplier", "vendor")
    inv_col = col_idx("invoice", "bill")
    price_col = col_idx("price", "rate", "cost")

    for r in raw_rows[1:]:
        if not any(r) or len(r) <= max(ing_col, 0):
            continue

        raw_name = r[ing_col].strip() if ing_col >= 0 and len(r) > ing_col else ""
        if not raw_name:
            continue

        iid, std_name, conf = match_ingredient(raw_name, ingredients)

        def parse_num(idx):
            if idx >= 0 and len(r) > idx:
                val = re.sub(r"[^\d.]", "", r[idx].strip())
                try:
                    return float(val) if val else 0.0
                except ValueError:
                    return 0.0
            return 0.0

        op_val = parse_num(open_col)
        rec_val = parse_num(rec_col)
        cl_val = parse_num(close_col)
        pr_val = parse_num(price_col)
        supp_name = r[supp_col].strip() if supp_col >= 0 and len(r) > supp_col else ""
        inv_no = r[inv_col].strip() if inv_col >= 0 and len(r) > inv_col else ""

        rows.append({
            "ingredient_id": iid,
            "raw_name": raw_name,
            "name": std_name,
            "opening_qty": op_val,
            "received_qty": rec_val,
            "closing_qty": cl_val,
            "supplier_name": supp_name,
            "invoice_no": inv_no,
            "unit_price_rs": pr_val,
            "confidence": conf,
            "flags": ["UNCERTAIN_MATCH"] if conf < 0.7 else []
        })

    return rows


def parse_xlsx(data: bytes, ingredients: list) -> list:
    if not openpyxl:
        return []
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.active
    rows_data = []
    for row in ws.iter_rows(values_only=True):
        if any(row):
            rows_data.append([str(c or "").strip() for c in row])
    if not rows_data:
        return []

    # Reuse CSV header parsing on stringified matrix
    header = [c.lower() for c in rows_data[0]]

    def col_idx(*names):
        for idx, h in enumerate(header):
            for n in names:
                if n in h:
                    return idx
        return -1

    ing_col = col_idx("ingredient", "item", "product", "name")
    open_col = col_idx("opening", "start")
    rec_col = col_idx("received", "delivery", "billed_qty", "qty", "quantity")
    close_col = col_idx("closing", "end", "physical")
    supp_col = col_idx("supplier", "vendor")
    inv_col = col_idx("invoice", "bill")
    price_col = col_idx("price", "rate", "cost")

    result = []
    for r in rows_data[1:]:
        raw_name = r[ing_col] if ing_col >= 0 and len(r) > ing_col else ""
        if not raw_name:
            continue
        iid, std_name, conf = match_ingredient(raw_name, ingredients)

        def parse_num(idx):
            if idx >= 0 and len(r) > idx:
                val = re.sub(r"[^\d.]", "", r[idx].strip())
                try:
                    return float(val) if val else 0.0
                except ValueError:
                    return 0.0
            return 0.0

        result.append({
            "ingredient_id": iid,
            "raw_name": raw_name,
            "name": std_name,
            "opening_qty": parse_num(open_col),
            "received_qty": parse_num(rec_col),
            "closing_qty": parse_num(close_col),
            "supplier_name": r[supp_col] if supp_col >= 0 and len(r) > supp_col else "",
            "invoice_no": r[inv_col] if inv_col >= 0 and len(r) > inv_col else "",
            "unit_price_rs": parse_num(price_col),
            "confidence": conf,
            "flags": ["UNCERTAIN_MATCH"] if conf < 0.7 else []
        })
    return result


def parse_pdf(data: bytes, ingredients: list) -> list:
    if not pypdf:
        return []
    reader = pypdf.PdfReader(io.BytesIO(data))
    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"

    rows = []
    lines = full_text.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        # Check if line mentions any known ingredient
        for ing in ingredients:
            if ing["name"].lower() in line_clean.lower() or ing["ingredient_id"].lower() in line_clean.lower():
                # Extract numeric quantities
                nums = [float(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b", line_clean)]
                op_qty = nums[0] if len(nums) > 0 else 0.0
                rec_qty = nums[1] if len(nums) > 1 else 0.0
                cl_qty = nums[2] if len(nums) > 2 else 0.0
                rows.append({
                    "ingredient_id": ing["ingredient_id"],
                    "raw_name": ing["name"],
                    "name": ing["name"],
                    "opening_qty": op_qty,
                    "received_qty": rec_qty,
                    "closing_qty": cl_qty,
                    "supplier_name": "",
                    "invoice_no": "",
                    "unit_price_rs": 0.0,
                    "confidence": 0.85,
                    "flags": []
                })
                break
    return rows


def parse_image(data: bytes, ingredients: list) -> tuple:
    """
    Validates uploaded JPEG/PNG image structure and integrity.
    NOTE: Optical Character Recognition (OCR) is NOT implemented.
    Generates a manual review template with zeroed quantities and explicit flags.
    """
    img = Image.open(io.BytesIO(data))
    img.verify()  # Validates image format integrity

    # Generate manual entry template rows for staff verification
    draft_rows = []
    for ing in ingredients:
        draft_rows.append({
            "ingredient_id": ing["ingredient_id"],
            "raw_name": ing["name"],
            "name": ing["name"],
            "opening_qty": 0.0,
            "received_qty": 0.0,
            "closing_qty": 0.0,
            "supplier_name": "",
            "invoice_no": "",
            "unit_price_rs": 0.0,
            "confidence": 0.0,
            "flags": ["MANUAL_ENTRY_REQUIRED", "IMAGE_OCR_UNAVAILABLE"]
        })
    return draft_rows, "Image uploaded successfully. Scanned image OCR is not implemented; manual staff verification and keying required."


def extract_document(data: bytes, filename: str, workflow_type: str, ingredients: list) -> dict:
    """
    Master extraction coordinator.
    Returns: {
        "file_type": ...,
        "file_hash": ...,
        "status": ...,
        "rows": [...],
        "notes": ...
    }
    """
    file_type = detect_file_type(data, filename)
    file_hash = calculate_sha256(data)
    rows = []
    notes = ""

    if file_type == "csv":
        rows = parse_csv(data, ingredients)
        status = "NEEDS_REVIEW" if rows else "EXTRACTION_FAILED"
    elif file_type == "xlsx":
        rows = parse_xlsx(data, ingredients)
        status = "NEEDS_REVIEW" if rows else "EXTRACTION_FAILED"
    elif file_type == "pdf":
        rows = parse_pdf(data, ingredients)
        status = "NEEDS_REVIEW" if rows else "EXTRACTION_FAILED"
    elif file_type in ("jpeg", "png"):
        rows, notes = parse_image(data, ingredients)
        status = "NEEDS_REVIEW"
    else:
        status = "EXTRACTION_FAILED"
        notes = "Unsupported format"

    # Save original document to disk
    ensure_upload_dir()
    saved_filename = f"{uuid.uuid4().hex}_{filename}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(data)

    return {
        "file_type": file_type,
        "file_hash": file_hash,
        "file_size_bytes": len(data),
        "status": status,
        "rows": rows,
        "raw_document_path": saved_path,
        "notes": notes
    }
