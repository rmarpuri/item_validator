"""
Perfume Inventory Validator — Orchestrator
Runs every Friday via GitHub Actions.

Pipeline: Gmail → Parse CSV → Serper Search → Gemini 3.1 Flash Lite Validate → Email Reply + CSV
"""

import os
import json
import re
import time
import base64
import csv
import io
import logging
from datetime import datetime
from typing import Optional

import google.generativeai as genai
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env when running locally; no effect in GitHub Actions
except ImportError:
    pass

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────────
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
SERPER_API_KEY    = os.environ["SERPER_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]          
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"] 
NOTIFY_EMAIL      = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)
CSV_FIELDNAMES   = []

# ── Naming convention rules (Synchronized with naming_rules.json) ──────────────
NAMING_RULES = """
PERFUME INVENTORY NAMING CONVENTION:
- Format: [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML
- All corrected names must be UPPERCASE — every character in every field must be uppercase
- Valid Types: EDP, EDT, EDC, PARFUM, COLOGNE
- Valid Genders: M, W, PH, UNISEX
- Use short-form brand normalization: 
    * DOLCE & GABBANA / DOLCE AND GABBANA / DOLCE&GABBANA → D&G
    * JEAN PAUL GAULTIER → JPG
    * CAROLINA HERRERA → CH
- Do not alter the original employee-entered name in the input CSV.

PRODUCT TYPE CONSTRAINTS:
- VIAL: Name MUST end with VIAL. Size MUST be less than 5ML.
- MINI: Name MUST end with MINI. Size MUST be between 5ML and 12ML (inclusive).
- MINI SET: Name MUST end with MINI SET. Formatted as [QTY] X [SIZE]ML MINI SET.
- TESTER: Name MUST end with TESTER.
- GIFTSET (SAME FRAGRANCE): Do NOT include the words GIFTSET or GIFT SET anywhere. List components with + after fragrance name (e.g. CHANEL NO5 EDP 100ML + 50ML).
- GIFTSET (DIFFERENT FRAGRANCES): Each component uses SHORT FRAGRANCE NAME + SIZE separated by + (e.g. CH 212 M EDT 100ML + CH 212 W EDP 75ML).
"""

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — EMAIL READER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_inventory_email() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Reads the latest inventory email from Gmail using IMAP."""
    import imaplib
    import email
    from email.header import decode_header

    log.info("Connecting to Gmail via IMAP...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        search_criteria = ['(SUBJECT "inventory")', '(SUBJECT "new items")', '(SUBJECT "fragrance")', '(SUBJECT "perfume")', '(SUBJECT "stock")']
        all_ids = []
        for criteria in search_criteria:
            _, data = mail.search(None, criteria)
            if data[0]:
                all_ids.extend(data[0].split())

        if not all_ids:
            log.warning("No inventory email found in inbox.")
            mail.logout()
            return None, None, None

        latest_id = sorted(set(all_ids))[-1]
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject_raw = msg["Subject"] or "Inventory"
        subject = decode_header(subject_raw)[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()

        sender = msg.get("From", "")
        log.info(f"Found email: '{subject}' from {sender}")

        csv_content = None
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename() or ""

            if any(ext in filename.lower() for ext in [".csv", ".xlsx", ".xls"]):
                payload = part.get_payload(decode=True)
                if filename.lower().endswith(".csv"):
                    csv_content = payload.decode("utf-8", errors="replace")
                elif filename.lower().endswith((".xlsx", ".xls")):
                    csv_content = excel_to_csv(payload)
                break
            elif content_type == "text/plain" and not csv_content:
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                if "," in body and "\n" in body and len(body.strip().split("\n")) > 2:
                    csv_content = body

        mail.logout()
        return csv_content, subject, sender
    except Exception as e:
        log.error(f"Gmail IMAP error: {e}")
        raise

def excel_to_csv(excel_bytes: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    output = io.StringIO()
    writer = csv.writer(output)
    for row in ws.iter_rows(values_only=True):
        writer.writerow([str(v) if v is not None else "" for v in row])
    return output.getvalue()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PARSE CSV
# ══════════════════════════════════════════════════════════════════════════════

def parse_csv(csv_text: str) -> list[dict]:
    global CSV_FIELDNAMES
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    CSV_FIELDNAMES = reader.fieldnames or []
    return [row for row in reader]

def get_item_name(item: dict) -> str:
    """Safely extract only the product name string from a CSV row."""
    # 1. Try to find the dedicated description/name column safely
    for key, val in item.items():
        # Ensure the key exists and is a string before checking
        if key and isinstance(key, str):
            if any(k in key.lower() for k in ["description", "name", "item", "fragrance"]):
                if val and isinstance(val, str) and val.strip():
                    return val.strip()
                    
    # 2. Fallback: Return the very first valid text value in the row
    for val in item.values():
        if val and isinstance(val, str) and val.strip():
            return val.strip()
            
    return "Unknown Item"

def get_item_search_key(item: dict) -> str:
    for key in item:
        if any(k in key.lower() for k in ["gtin", "ean", "upc", "barcode"]):
            val = item[key].strip()
            if val: return val
    return get_item_name(item)

def get_input_country_origin(item: dict) -> str:
    for key in item:
        if any(k in key.lower() for k in ["origin", "country", "coo"]):
            val = item[key].strip()
            if val: return val.upper()
    return ""

def normalize_short_forms(name: str, item: dict) -> str:
    if not name: return name
    original = get_item_name(item).upper()
    replacements = {
        "DOLCE & GABBANA": "D&G", "DOLCE AND GABBANA": "D&G", "DOLCE&GABBANA": "D&G",
        "SALVATORE FERRAGAMO": "S FERRAGAMO", "JEAN PAUL GAULTIER": "JPG", "CAROLINA HERRERA": "CH",
    }
    for long_form, short_form in replacements.items():
        if long_form in name or short_form in original:
            name = re.sub(rf"\b{re.escape(long_form)}\b", short_form, name)
    return name

def is_giftset_name(name: str) -> bool:
    if not name: return False
    upper = name.upper()
    if "GIFT SET" in upper or "GIFTSET" in upper or re.search(r"\b\d+\s*PCS\b", upper): return True
    if "+" in upper:
        return len(re.findall(r"\d+(?:\.\d+)?\s*ML\b", upper)) >= 2
    return False

def normalize_giftset_name(name: str) -> str:
    if not name: return name
    normalized = re.sub(r"\bGIFT\s*SET\b", "", name, flags=re.IGNORECASE)
    normalized = re.sub(r"\bGIFTSET\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*\+\s*", " + ", normalized)
    return " ".join(normalized.split()).strip("+ ").strip()

def normalize_corrected_name(corrected_name: str, item: dict) -> str:
    if not corrected_name: return corrected_name
    corrected_name = corrected_name.strip().upper()
    corrected_name = normalize_short_forms(corrected_name, item)
    return normalize_giftset_name(corrected_name)

def brand_matches_original(brand: str, original_entry: str) -> bool:
    if not brand: return False
    b, orig = brand.strip().upper(), (original_entry or "").upper()
    if b in orig: return True
    known_long_forms = {"DOLCE & GABBANA": "D&G", "DOLCE AND GABBANA": "D&G", "JEAN PAUL GAULTIER": "JPG", "CAROLINA HERRERA": "CH"}
    for long_form, short in known_long_forms.items():
        if short == b and (long_form in orig or short in orig): return True
    tokens = re.split(r"[\s\-]+", orig)
    return bool(tokens and tokens[0] and tokens[0] in b)

def extract_first_url(text: str) -> str:
    if not text: return ""
    match = re.search(r"https?://[^\s\)\]\"]+", text)
    return match.group(0).strip() if match else ""

def normalize_source_name(source: str) -> str:
    if not source: return ""
    source = re.sub(r"^https?://", "", source.strip(), flags=re.IGNORECASE)
    source = re.sub(r"^www\.", "", source, flags=re.IGNORECASE).split("/")[0]
    return re.sub(r"\.(com|net|org|io|co|fr|de|uk)$", "", source, flags=re.IGNORECASE)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — AGENT 2: SMART SEARCH
# ══════════════════════════════════════════════════════════════════════════════

TRUSTED_SITES = [
    ("ebay.com",             10),  
    ("jomashop.com",          9),  
    ("fragrancenet.com",      8),  
    ("sephora.com",           8),  
    ("nordstrom.com",         8),  
    ("fragrantica.com",       8),  
    ("basenotes.net",         7),  
    ("parfumo.com",           7),  
]
TRUSTED_DOMAINS = {site: score for site, score in TRUSTED_SITES}

def get_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def trust_score(url: str) -> int:
    domain = get_domain(url)
    for trusted_domain, score in TRUSTED_DOMAINS.items():
        if trusted_domain in domain: return score
    return 0

def serper_search_raw(query: str, num: int = 5) -> dict:
    try:
        # Ensure this URL is exactly a plain string with NO markdown brackets
        url = "https://google.serper.dev/search"
        
        res = requests.post(
            url,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num}, 
            timeout=10,
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        log.warning(f"Serper search error for '{query}': {e}")
        return {}

def parse_serper_results(data: dict) -> list[dict]:
    results = []
    for r in data.get("organic", []):
        url = r.get("link", "")
        results.append({
            "title":        r.get("title", ""),
            "url":          url,
            "snippet":      r.get("snippet", ""),
            "trust_score":  trust_score(url),
            "source_label": get_domain(url) or "unknown",
        })
    return results

def format_results_for_llm(results: list[dict], item_name: str) -> str:
    if not results: return "No results found from any source."
    sorted_results = sorted(results, key=lambda x: x["trust_score"], reverse=True)
    lines = [f"SEARCH RESULTS FOR: {item_name}", ""]
    for i, r in enumerate(sorted_results[:6], 1):  
        lines.append(f"[{i}] {r['title']}\n    Source : {r['source_label']} [Trust: {r['trust_score']}]\n    URL    : {r['url']}\n    Info   : {r['snippet']}\n")
    return "\n".join(lines)

def search_product(item_name: str) -> str:
    all_results = []

    ebay_data = serper_search_raw(f"site:ebay.com {item_name} perfume")
    ebay_results = [r for r in parse_serper_results(ebay_data) if r["trust_score"] == 10]
    if ebay_results:
        log.info(f"  ✓ Found {len(ebay_results)} authoritative records on eBay")
        all_results.extend(ebay_results)

    joma_data = serper_search_raw(f"site:jomashop.com {item_name} perfume")
    joma_results = [r for r in parse_serper_results(joma_data) if r["trust_score"] == 9]
    if joma_results:
        log.info(f"  ✓ Found {len(joma_results)} fallback records on Jomashop")
        all_results.extend(joma_results)

    if not all_results:
        broad_data = serper_search_raw(f"{item_name} perfume fragrance EDP EDT ml", num=5)
        all_results.extend(parse_serper_results(broad_data))

    return format_results_for_llm(deduplicate_results(all_results), item_name)

def deduplicate_results(results: list[dict]) -> list[dict]:
    seen_domains = {}
    for r in sorted(results, key=lambda x: x["trust_score"], reverse=True):
        domain = get_domain(r["url"]) or r["source_label"]
        if domain not in seen_domains: seen_domains[domain] = r
    return list(seen_domains.values())

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — AGENT 3: VALIDATOR (Adaptive Quota Control Guard)
# ══════════════════════════════════════════════════════════════════════════════

def validate_with_gemini_with_retry(item: dict, search_result: str, max_retries: int = 5) -> dict:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=(
            "You are a perfume validation bot. Return structural JSON only. "
            "Examine search text payload fields to deduce the country where the fragrance was manufactured. "
            "Return the two-character ISO code for country of origin in 'country_of_origin' field (e.g., FR, IT, US, ES)."
        ),
    )

    prompt = f"""
NAMING CONVENTION:
{NAMING_RULES}

EMPLOYEE ENTERED:
{json.dumps(item, indent=2)}

SEARCH PAYLOAD TEXT:
{search_result}

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "corrected_name": "FULL CORRECTED NAME PER CONVENTION",
  "brand": "BRAND NAME",
  "fragrance": "FRAGRANCE NAME ONLY",
  "size_ml": "E.G. 100ML",
  "type": "EDP|EDT|EDC|PARFUM|COLOGNE|BL",
  "gender": "M|W|PH|UNISEX",
  "country_of_origin": "ISO 2-letter manufacturing country code deduced from data e.g. FR, IT, US",
  "source_used": "domain name of validation target",
  "remarks": "base remark summaries",
  "confidence": "High|Medium|Low",
  "needs_review": false
}}
"""
    base_delay = 6.0  
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            err_msg = str(e)
            if any(k in err_msg for k in ["429", "Quota", "ResourceExhausted"]):
                wait = base_delay * (2 ** (attempt - 1))
                
                match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", err_msg)
                if match: 
                    wait = float(match.group(1)) + 2.0
                else:
                    match_alt = re.search(r"Please retry in (\d+(?:\.\d+)?)s", err_msg)
                    if match_alt:
                        wait = float(match_alt.group(1)) + 2.0

                log.warning(f"  ⚠️ [Attempt {attempt}/{max_retries}] Gemini Quota Limit hit. Sleeping {wait:.2f}s...")
                time.sleep(wait)
            else:
                raise e
                
    return {"corrected_name": get_item_name(item), "remarks": "Rate limit failure", "needs_review": True}

def validate_with_gemini(item: dict, search_result: str) -> dict:
    try:
        validation = validate_with_gemini_with_retry(item, search_result)
        
        corrected_name = validation.get("corrected_name", "")
        normalized_name = normalize_corrected_name(corrected_name, item)
        if normalized_name and normalized_name != corrected_name:
            validation["corrected_name"] = normalized_name

        if validation.get("corrected_name"):
            corrected_name = validation["corrected_name"].upper()
            required_type = validation.get("type", "").upper()
            required_size = validation.get("size_ml", "").upper()
            
            cat_code = item.get("Item Category Code", "").upper()
            suffix_to_append = next((s for s in ["VIAL", "MINI SET", "MINI", "TESTER"] if cat_code in [s+"S", "MINIATURES"]), "")
            
            if suffix_to_append and corrected_name.endswith(suffix_to_append):
                corrected_name = corrected_name[:-len(suffix_to_append)].strip()

            if required_type and required_type not in corrected_name and not is_giftset_name(corrected_name):
                corrected_name = f"{corrected_name} {required_type}"
            if required_size and required_size not in corrected_name and not is_giftset_name(corrected_name):
                corrected_name = f"{corrected_name} {required_size}"
            if suffix_to_append:
                corrected_name = f"{corrected_name} {suffix_to_append}"
            
            validation["corrected_name"] = " ".join(corrected_name.split())

        input_coo = get_input_country_origin(item)
        online_coo = validation.get("country_of_origin", "").strip().upper()
        
        origin_remark = ""
        if online_coo:
            if input_coo and input_coo != online_coo:
                origin_remark = f"Origin mismatch: {input_coo} vs {online_coo}"
                validation["needs_review"] = True  
            elif input_coo == online_coo:
                origin_remark = f"Origin verified: {online_coo}"
        
        current_remarks = validation.get("remarks", "")
        if origin_remark:
            if current_remarks in (None, "", "OK"):
                validation["remarks"] = origin_remark
            else:
                validation["remarks"] = f"{current_remarks} | {origin_remark}"

        if not validation.get("source_url"):
            url = extract_first_url(search_result)
            if url:
                validation["source_url"] = url
                if not validation.get("source_used"):
                    validation["source_used"] = normalize_source_name(get_domain(url))

        return validation
    except Exception as e:
        return {"corrected_name": get_item_name(item), "remarks": f"Process error: {e}", "needs_review": True}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — ORCHESTRATOR LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_validation(items: list[dict]) -> list[dict]:
    results = []
    for item in items:
        item_name = get_item_name(item)
        search_data = search_product(item_name)
        
        log.info("  ⏳ Pacing window delay restriction: sleeping 5.2 seconds...")
        time.sleep(5.2)

        validation = validate_with_gemini(item, search_data)
        results.append({"original_entry": item_name, "original_data": item, **validation})
    return results

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — OUTPUT AGENT
# ══════════════════════════════════════════════════════════════════════════════

def results_to_csv(results: list[dict]) -> str:
    if not results: return ""
    original_fields = [f for f in list(results[0].get("original_data", {}).keys()) if f and f.strip()]
    extra_fields = ["Corrected Name", "Gender", "Remarks", "Source Used", "Confidence", "Needs Review"]
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=original_fields + extra_fields)
    writer.writeheader()

    for r in results:
        row = {k: r.get("original_data", {}).get(k, "") for k in original_fields}
        url = r.get("source_url", "")
        label = normalize_source_name(r.get("source_used") or url)
        
        row.update({
            "Corrected Name": r.get("corrected_name", ""),
            "Gender":         r.get("gender", ""),
            "Remarks":        r.get("remarks", ""),
            "Source Used":    f'=HYPERLINK("{url}", "{label}")' if url else label,
            "Confidence":     r.get("confidence", ""),
            "Needs Review":   "YES" if r.get("needs_review") else "NO",
        })
        writer.writerow(row)
    return output.getvalue()

def compute_stats(results: list[dict]) -> dict:
    review = [r for r in results if r.get("needs_review") or "mismatch" in str(r.get("remarks")).lower()]
    return {
        "total": len(results),
        "ok": len([r for r in results if r.get("remarks") == "OK"]),
        "corrected": len([r for r in results if not r.get("needs_review") and r.get("remarks") != "OK"]),
        "review": len(review),
        "review_items": [r["original_entry"] for r in review],
    }

def main():
    csv_text, subject, sender = fetch_inventory_email()
    if not csv_text: return log.error("No input data file payload located.")

    items = parse_csv(csv_text)
    results = run_validation(items)
    csv_output = results_to_csv(results)
    
    os.makedirs("output", exist_ok=True)
    with open("output/test_output.csv", "w", encoding="utf-8") as f:
        f.write(csv_output)

    stats = compute_stats(results)
    log.info(f"Processing complete. total run items: {stats['total']} | reviews flagged: {stats['review']}")

if __name__ == "__main__":
    main()