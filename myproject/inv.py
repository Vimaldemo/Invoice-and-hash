import pdfplumber
import re
import json
import sys
import os


def _first_match(patterns, text, flags=re.IGNORECASE):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            # return the first non-empty capturing group if present
            for g in m.groups():
                if g:
                    return g.strip()
            return m.group(0).strip()
    return None

def _safe_float_amount(amount_text):
    if not amount_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", amount_text)
    if not cleaned:
        return None
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = parts[0] + "." + "".join(parts[1:])
    try:
        return float(cleaned)
    except Exception:
        return None


def _extract_text_pdfplumber(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text += page_text + "\n"
    return text


def _extract_text_fitz(pdf_path):
    try:
        import fitz
    except Exception:
        return ""
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                page_text = page.get_text("text") or ""
                if page_text:
                    text += page_text + "\n"
    except Exception:
        return ""
    return text


def _extract_text_ocr(pdf_path):
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return ""

    poppler_path = os.environ.get("POPPLER_PATH") or os.environ.get("POPPLER_BIN")
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        except Exception:
            pass

    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
    except Exception:
        try:
            images = convert_from_path(pdf_path, dpi=300)
        except Exception:
            return ""

    text = ""
    for img in images:
        try:
            page_text = pytesseract.image_to_string(img, config="--psm 3")
        except Exception:
            page_text = ""
        if page_text:
            text += page_text + "\n"
    return text


def _text_score(text):
    if not text:
        return 0
    printable = sum(1 for ch in text if ch.isprintable())
    alnum = sum(1 for ch in text if ch.isalnum())
    if printable <= 0:
        return 0
    ratio = alnum / max(printable, 1)
    return alnum + int(1000 * ratio)


def _get_best_text(pdf_path):
    candidates = []
    try:
        candidates.append(("pdfplumber", _extract_text_pdfplumber(pdf_path)))
    except Exception:
        candidates.append(("pdfplumber", ""))
    candidates.append(("fitz", _extract_text_fitz(pdf_path)))

    best_method = None
    best_text = ""
    best_score = 0
    for method, text in candidates:
        score = _text_score(text)
        if score > best_score:
            best_score = score
            best_method = method
            best_text = text

    if best_score < 200:
        ocr_text = _extract_text_ocr(pdf_path)
        ocr_score = _text_score(ocr_text)
        if ocr_score > best_score:
            best_method = "ocr"
            best_text = ocr_text

    return best_method, best_text or ""


def extract_invoice_details(pdf_path):
    extraction_method, raw_text = _get_best_text(pdf_path)
    text = re.sub(r"[ \t]+", " ", raw_text)
    text_one_line = re.sub(r"\s+", " ", raw_text)

    # Patterns
    invoice_number_patterns = [
        r"(?im)\b(?:tax\s*)?invoice\s*(?:no\.?|number|#|num)\s*[:\-\.]?\s*([A-Za-z0-9]+(?:\s*[/\-]\s*[A-Za-z0-9]+)+)\b",
        r"(?im)\binv\.?\s*no\.?\s*[:\-\.]?\s*([A-Za-z0-9]+(?:\s*[/\-]\s*[A-Za-z0-9]+)+)\b",
        r"(?im)\bbill\s*(?:no\.?|number|#)\s*[:\-\.]?\s*([A-Za-z0-9]+(?:\s*[/\-]\s*[A-Za-z0-9]+)+)\b",
        r"(?im)\b(?:tax\s*)?invoice\s*(?:no\.?|number|#|num)\s*[:\-\.]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
        r"(?im)\binv\.?\s*no\.?\s*[:\-\.]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
        r"(?im)\bbill\s*(?:no\.?|number|#)\s*[:\-\.]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
        r"(?im)\bdocument\s*(?:no\.?|number)\s*[:\-\.]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
        r"(?im)\bref(?:erence)?\s*(?:no\.?|number)\s*[:\-\.]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
    ]

    # Date patterns: numeric and textual months
    date_patterns = [
        r"(?im)\b(?:invoice\s*date|date\s*of\s*issue|dated)\b\s*[:\-]?\s*(\d{4}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{1,2})\b",
        r"(?im)\b(?:invoice\s*date|date\s*of\s*issue|dated)\b\s*[:\-]?\s*(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})\b",
        r"(?im)\b(?:invoice\s*date|date\s*of\s*issue|dated)\b\s*[:\-]?\s*(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*\d{2,4})\b",
        r"(?im)\b(?:invoice\s*date|date\s*of\s*issue|dated)\b\s*[:\-]?\s*(\d{1,2}\s*[-\/\.]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*[-\/\.]\s*\d{2,4})\b",
        r"(?im)\b(?:ack\s*date)\b\s*[:\-]?\s*(\d{1,2}\s*[-\/\.]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*[-\/\.]\s*\d{2,4})\b",
        r"(?im)\bdate\b\s*[:\-]?\s*(\d{4}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{1,2})\b",
        r"(?im)\bdate\b\s*[:\-]?\s*(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})\b",
        r"(?im)\bdate\b\s*[:\-]?\s*(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*\d{2,4})\b",
        r"(?im)\bdate\b\s*[:\-]?\s*(\d{1,2}\s*[-\/\.]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*[-\/\.]\s*\d{2,4})\b",
    ]

    invoice_id_patterns = [
        r"(?im)\binvoice\s*id\b\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})\b",
        r"(?im)\birn\b\s*[:\-]?\s*([0-9a-f]{64})\b",
        r"(?im)\b(?:ack(?:nowledg(e)?ment)?\s*no\.?|ack\s*no\.?)\b\s*[:\-]?\s*([A-Za-z0-9\-\/]{4,})\b",
        r"(?im)\b(?:uuid|unique\s*id)\b\s*[:\-]?\s*([A-Za-z0-9\-]{8,})\b",
    ]

    total_patterns = [
        r"(?im)\bgrand\s*total\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\binvoice\s*total\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\btotal\s*(?:amount|payable)?\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\bamount\s*due\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\bbalance\s*due\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\bnet\s*amount\b.*?(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\btotal\b\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
        r"(?im)\btotal\b.*?(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b",
    ]

    invoice_number = _first_match(invoice_number_patterns, text)
    if invoice_number:
        invoice_number = re.sub(r"\s+", " ", invoice_number).strip()
        invoice_number = re.sub(r"\s*([/\-])\s*", r"\1", invoice_number)
    # Fallback: many invoices use codes like 'P24251106' (alpha + digits)
    if not invoice_number:
        # collect candidates like 'P24251106' (letters+digits)
        candidates = re.findall(r"\b[A-Za-z]*\d{5,}[A-Za-z0-9\-\/]*\b", text_one_line)
        if candidates:
            if len(candidates) == 1:
                invoice_number = candidates[0]
            else:
                # prefer a candidate nearest the word 'Invoice'
                invoice_pos = [m.start() for m in re.finditer(r"invoice", text_one_line, re.IGNORECASE)]
                if invoice_pos:
                    best = None
                    best_dist = None
                    for c in candidates:
                        for m in re.finditer(re.escape(c), text_one_line):
                            pos = m.start()
                            dist = min([abs(pos - p) for p in invoice_pos])
                            if best is None or dist < best_dist:
                                best = c
                                best_dist = dist
                    invoice_number = best
                else:
                    # fallback: pick the longest candidate
                    invoice_number = max(candidates, key=len)
    invoice_date = _first_match(date_patterns, text)
    invoice_id = _first_match(invoice_id_patterns, text)

    total_amount = _first_match(total_patterns, text)
    if not total_amount:
        amount_candidates = []
        for m in re.finditer(r"(?im)\b(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b", text):
            amount_candidates.append(m.group(1))
        if amount_candidates:
            amount_candidates_sorted = sorted(
                amount_candidates,
                key=lambda v: (_safe_float_amount(v) is not None, _safe_float_amount(v) or 0),
                reverse=True,
            )
            total_amount = amount_candidates_sorted[0]

    # Clean amount
    if total_amount:
        total_amount = total_amount.replace(",", "").strip()

    data = {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "invoice_id": invoice_id,
        "total_amount": total_amount,
        "source_file": os.path.basename(pdf_path),
        "extraction_method": extraction_method,
    }

    return data


def save_as_json(data, pdf_path):
    out_path = os.path.splitext(pdf_path)[0] + ".invoice.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        pdf_file = sys.argv[1]
    else:
        print("Usage: python inv.py <path-to-invoice.pdf>")
        sys.exit(1)

    if not os.path.isfile(pdf_file):
        print(f"File not found: {pdf_file}")
        sys.exit(1)

    result = extract_invoice_details(pdf_file)
    print(json.dumps(result, indent=4, ensure_ascii=False))
    out = save_as_json(result, pdf_file)
    print(f"Saved extraction to: {out}")