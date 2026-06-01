"""
Perfume Inventory Validator — Orchestrator
Runs every Friday via GitHub Actions.

Agents:
  Agent 1 — Email Reader     (agents/agent1_email_reader.md)
  Agent 2 — Smart Search     (agents/agent2_smart_search.md)
  Agent 3 — Validator        (agents/agent3_validator.md)
  Agent 4 — Output           (agents/agent4_output.md)

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
GMAIL_USER        = os.environ["GMAIL_USER"]          # your.email@company.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"] # Gmail App Password (not login password)
NOTIFY_EMAIL      = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)
CSV_FIELDNAMES   = []

# ── Agent instruction loader ──────────────────────────────────────────────────
def load_agent_instructions(agent_file: str) -> str:
    """Load agent instruction markdown from agents/ folder."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "agents", agent_file)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        log.warning(f"Agent instructions not found: {path}")
        return ""

# ── Naming convention rules (Synchronized with naming_rules.json) ──────────────
NAMING_RULES = """
PERFUME INVENTORY NAMING CONVENTION:
- Format: [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML
- All corrected names must be UPPERCASE — every character in every field must be uppercase
- Valid Types: EDP, EDT, EDC, PARFUM, COLOGNE
- Valid Genders (Derived from image specifications): M, W, PH, UNISEX
- Use short-form brand normalization: 
    * DOLCE & GABBANA / DOLCE AND GABBANA / DOLCE&GABBANA → D&G
    * JEAN PAUL GAULTIER → JPG
    * CAROLINA HERRERA → CH
- Do not alter the original employee-entered name in the input CSV.
- Build `remarks` fields as an exact audit trail using standard codes joined by " | ".

PRODUCT TYPE CONSTRAINTS:
- VIAL: Name MUST end with VIAL. Size MUST be less than 5ML.
- MINI: Name MUST end with MINI. Size MUST be between 5ML and 12ML (inclusive).
- MINI SET: Name MUST end with MINI SET. Formatted as [QTY] X [SIZE]ML MINI SET.
- TESTER: Name MUST end with TESTER.
- GIFTSET (SAME FRAGRANCE): Do NOT include the words GIFTSET or GIFT SET anywhere. List components with + after fragrance name (e.g. CHANEL NO5 EDP 100ML + 50ML).
- GIFTSET (DIFFERENT FRAGRANCES): Each component uses SHORT FRAGRANCE NAME + SIZE separated by + (e.g. CH 212 M EDT 100ML + CH 212 W EDP 75ML).

COMMON ABBREVIATIONS MAPPING (Case-Insensitive Input Processing):
- "POUR HOMME" / "POUR FEMME" → "PH"
- "EAU DE PARFUM" / "edp" → "EDP"
- "EAU DE TOILETTE" / "edt" → "EDT"
- "EAU DE COLOGNE" / "edc" → "EDC"
- "MEN" / "MAN" → "M"
- "WOMEN" / "WOMAN" → "W"
"""

# ── Load agent instructions at startup ────────────────────────────────────────
AGENT1_INSTRUCTIONS = load_agent_instructions("agent1_email_reader.md")
AGENT2_INSTRUCTIONS = load_agent_instructions("agent2_smart_search.md")
AGENT3_INSTRUCTIONS = load_agent_instructions("agent3_validator.md")
AGENT4_INSTRUCTIONS = load_agent_instructions("agent4_output.md")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — AGENT 1: EMAIL READER
# See: agents/agent1_email_reader.md
# ══════════════════════════════════════════════════════════════════════════════

def fetch_inventory_email() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Reads the latest inventory email from Gmail using IMAP.
    Returns (csv_content, subject, sender) or (None, None, None)
    """
    import imaplib
    import email
    from email.header import decode_header

    log.info("Connecting to Gmail via IMAP...")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        # Search for emails with inventory-related subjects
        search_criteria = [
            '(SUBJECT "inventory")',
            '(SUBJECT "new items")',
            '(SUBJECT "fragrance")',
            '(SUBJECT "perfume")',
            '(SUBJECT "stock")',
        ]

        all_ids = []
        for criteria in search_criteria:
            _, data = mail.search(None, criteria)
            if data[0]:
                all_ids.extend(data[0].split())

        if not all_ids:
            log.warning("No inventory email found in inbox.")
            mail.logout()
            return None, None, None

        # Get the most recent matching email
        latest_id = sorted(set(all_ids))[-1]
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Decode subject
        subject_raw = msg["Subject"] or "Inventory"
        subject = decode_header(subject_raw)[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()

        sender = msg.get("From", "")
        log.info(f"Found email: '{subject}' from {sender}")

        # Extract CSV/Excel attachment
        csv_content = None
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename() or ""

            if any(ext in filename.lower() for ext in [".csv", ".xlsx", ".xls"]):
                payload = part.get_payload(decode=True)
                log.info(f"Found attachment: {filename}")

                if filename.lower().endswith(".csv"):
                    csv_content = payload.decode("utf-8", errors="replace")
                elif filename.lower().endswith((".xlsx", ".xls")):
                    csv_content = excel_to_csv(payload)
                break

            # Also check inline CSV text
            elif content_type == "text/plain" and not csv_content:
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                # Heuristic: if it looks like CSV (has commas and newlines)
                if "," in body and "\n" in body and len(body.strip().split("\n")) > 2:
                    csv_content = body
                    log.info("Found inline CSV in email body")

        mail.logout()

        if not csv_content:
            log.warning("Email found but no CSV/Excel attachment detected.")
            return None, subject, sender

        return csv_content, subject, sender

    except Exception as e:
        log.error(f"Gmail IMAP error: {e}")
        raise


def excel_to_csv(excel_bytes: bytes) -> str:
    """Convert Excel bytes to CSV string using openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    output = io.StringIO()
    writer = csv.writer(output)
    for row in ws.iter_rows(values_only=True):
        writer.writerow([str(v) if v is not None else "" for v in row])
    return output.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PARSE CSV (feeds items into Agent 2 + Agent 3)
# ══════════════════════════════════════════════════════════════════════════════

def parse_csv(csv_text: str) -> list[dict]:
    """Parse CSV text into list of dicts."""
    global CSV_FIELDNAMES
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    CSV_FIELDNAMES = reader.fieldnames or []
    items = [row for row in reader]
    log.info(f"Parsed {len(items)} items from CSV")
    return items


def get_item_name(item: dict) -> str:
    """Extract the product name from a CSV row regardless of column naming."""
    for key in item:
        if any(k in key.lower() for k in ["description", "name", "item", "fragrance"]):
            val = item[key].strip()
            if val:
                return val
    # Fallback: first non-empty value
    return next((v.strip() for v in item.values() if v.strip()), "Unknown Item")


def get_item_search_key(item: dict) -> str:
    """Extract the best search key from a CSV row, preferring GTIN."""
    for key in item:
        if any(k in key.lower() for k in ["gtin", "ean", "upc", "barcode"]):
            val = item[key].strip()
            if val:
                return val

    # If no GTIN-style identifier is present, fall back to name/description.
    return get_item_name(item)


def normalize_short_forms(name: str, item: dict) -> str:
    """Preserve expected short-form brand abbreviations in corrected names."""
    if not name:
        return name

    original = get_item_name(item).upper()
    replacements = {
        "DOLCE & GABBANA": "D&G",
        "DOLCE AND GABBANA": "D&G",
        "DOLCE&GABBANA": "D&G",
        "SALVATORE FERRAGAMO": "S FERRAGAMO",
        "JEAN PAUL GAULTIER": "JPG",
        "CAROLINA HERRERA": "CH",
    }

    corrected = name
    for long_form, short_form in replacements.items():
        if long_form in corrected and short_form in original:
            corrected = re.sub(rf"\b{re.escape(long_form)}\b", short_form, corrected)
        elif short_form in original and long_form in corrected:
            corrected = re.sub(rf"\b{re.escape(long_form)}\b", short_form, corrected)
        elif short_form in corrected and long_form in original:
            corrected = re.sub(rf"\b{re.escape(long_form)}\b", short_form, corrected)
    return corrected


def is_giftset_name(name: str) -> bool:
    """Return True for giftset-like product names with multiple component volumes."""
    if not name:
        return False

    upper = name.upper()
    if "GIFT SET" in upper or "GIFTSET" in upper:
        return True
    if re.search(r"\b\d+\s*PCS\b", upper):
        return True

    if "+" in upper:
        sizes = re.findall(r"\d+(?:\.\d+)?\s*ML\b", upper)
        return len(sizes) >= 2

    return False


def normalize_giftset_name(name: str) -> str:
    """Remove gift set label and keep only the component size details."""
    if not name:
        return name

    normalized = re.sub(r"\bGIFT\s*SET\b", "", name, flags=re.IGNORECASE)
    normalized = re.sub(r"\bGIFTSET\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*\+\s*", " + ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized)
    normalized = normalized.strip()
    normalized = normalized.strip("+").strip()
    return normalized


def normalize_corrected_name(corrected_name: str, item: dict) -> str:
    """Apply final normalization rules to the corrected name."""
    if not corrected_name:
        return corrected_name

    corrected_name = corrected_name.strip().upper()
    corrected_name = normalize_short_forms(corrected_name, item)
    corrected_name = normalize_giftset_name(corrected_name)
    return corrected_name


def brand_matches_original(brand: str, original_entry: str) -> bool:
    """Heuristic: return True if proposed brand likely matches the original entry."""
    if not brand:
        return False
    b = brand.strip().upper()
    orig = (original_entry or "").upper()
    if b in orig:
        return True
    known_long_forms = {
        "DOLCE & GABBANA": "D&G",
        "DOLCE AND GABBANA": "D&G",
        "JEAN PAUL GAULTIER": "JPG",
        "CAROLINA HERRERA": "CH",
    }
    for long_form, short in known_long_forms.items():
        if short == b and (long_form in orig or short in orig):
            return True
    tokens = re.split(r"[\s\-]+", orig)
    if tokens and tokens[0] and tokens[0] in b:
        return True
    return False


def extract_first_url(text: str) -> str:
    """Return the first HTTP/HTTPS URL found in a search result text."""
    if not text:
        return ""
    match = re.search(r"https?://[^\s\)\]\"]+", text)
    return match.group(0).strip() if match else ""

def normalize_source_name(source: str) -> str:
    """Normalize domain-based source names for display in the CSV."""
    if not source:
        return ""
    source = source.strip()
    source = re.sub(r"^https?://", "", source, flags=re.IGNORECASE)
    source = re.sub(r"^www\.", "", source, flags=re.IGNORECASE)
    source = source.split("/")[0]
    source = re.sub(r"\.(com|net|org|io|co|fr|de|uk)$", "", source, flags=re.IGNORECASE)
    return source

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — AGENT 2: SMART SEARCH
# See: agents/agent2_smart_search.md
# ══════════════════════════════════════════════════════════════════════════════

TRUSTED_SITES = [
    ("ebay.com",             10),
    ("jomashop.com",         9),  
    ("fragrancenet.com",      9),  
    ("sephora.com",           9),  
    ("nordstrom.com",         9),  
    ("macys.com",             8),  
    ("bloomingdales.com",     8),  
    ("fragrancex.com",        8),  
    ("perfumania.com",        8),  
    ("beautycounter.com",     7),  
    ("feelunique.com",        7),  
    ("fragrantica.com",       9),  
    ("basenotes.net",         8),  
    ("parfumo.com",           7),  
]

TRUSTED_DOMAINS = {site: score for site, score in TRUSTED_SITES}


def get_domain(url: str) -> str:
    """Extract base domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain
    except Exception:
        return ""


def trust_score(url: str) -> int:
    """Return trust score for a URL. 0 = unknown site."""
    domain = get_domain(url)
    for trusted_domain, score in TRUSTED_DOMAINS.items():
        if trusted_domain in domain:
            return score
    return 0


def serper_search_raw(query: str, num: int = 5) -> dict:
    """Raw Serper API call — returns full JSON response."""
    try:
        res = requests.post(
            "https://google.serper.dev/search",
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
    """Parse Serper response into a flat list of result dicts."""
    results = []

    kg = data.get("knowledgeGraph", {})
    if kg.get("title"):
        kg_text = f"Title: {kg['title']}"
        if kg.get("type"):
            kg_text += f" | Type: {kg['type']}"
        if kg.get("description"):
            kg_text += f" | {kg['description']}"
        for k, v in (kg.get("attributes") or {}).items():
            kg_text += f" | {k}: {v}"
        results.append({
            "title":        kg.get("title", ""),
            "url":          kg.get("website", ""),
            "snippet":      kg_text,
            "trust_score":  10,
            "source_label": "Google Knowledge Graph",
        })

    for r in data.get("organic", []):
        url = r.get("link", "")
        score = trust_score(url)
        results.append({
            "title":        r.get("title", ""),
            "url":          url,
            "snippet":      r.get("snippet", ""),
            "trust_score":  score,
            "source_label": get_domain(url) or "unknown",
        })

    return results


def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove near-duplicate results by domain, keeping highest trust."""
    seen_domains = {}
    for r in sorted(results, key=lambda x: x["trust_score"], reverse=True):
        domain = get_domain(r["url"]) or r["source_label"]
        if domain not in seen_domains:
            seen_domains[domain] = r
    return list(seen_domains.values())


def format_results_for_llm(results: list[dict], item_name: str) -> str:
    """Format search results for the LLM with trust scores clearly marked."""
    if not results:
        return "No results found from any source."

    sorted_results = sorted(results, key=lambda x: x["trust_score"], reverse=True)
    lines = [f"SEARCH RESULTS FOR: {item_name}", ""]

    for i, r in enumerate(sorted_results[:6], 1):  
        trust_label = (
            "★★★ HIGHLY TRUSTED"  if r["trust_score"] >= 9 else
            "★★  TRUSTED"         if r["trust_score"] >= 7 else
            "★   MODERATE"        if r["trust_score"] >= 4 else
            "    UNKNOWN SOURCE"
        )
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    Source : {r['source_label']}  [{trust_label}]")
        lines.append(f"    URL    : {r['url']}")
        lines.append(f"    Info   : {r['snippet'][:200]}")
        lines.append("")

    return "\n".join(lines)


def search_product(item_name: str) -> str:
    """Multi-source smart search strategy."""
    log.info(f"  Searching: {item_name}")
    all_results = []

    data = serper_search_raw(f"site:jomashop.com {item_name} perfume")
    jomashop_results = parse_serper_results(data)
    trusted_jomashop = [r for r in jomashop_results if r["trust_score"] >= 8]

    if trusted_jomashop:
        log.info(f"  ✓ Found {len(trusted_jomashop)} results on Jomashop")
        all_results.extend(trusted_jomashop)
    else:
        log.info(f"  Jomashop miss — expanding search to trusted retailers")

        retailer_query = (
            f"{item_name} perfume EDP EDT ml "
            f"site:fragrancenet.com OR site:sephora.com OR site:nordstrom.com "
            f"OR site:fragrancex.com OR site:perfumania.com"
        )
        data2 = serper_search_raw(retailer_query, num=5)
        retailer_results = parse_serper_results(data2)
        trusted_retailers = [r for r in retailer_results if r["trust_score"] >= 7]

        if trusted_retailers:
            log.info(f"  ✓ Found {len(trusted_retailers)} results from trusted retailers")
            all_results.extend(trusted_retailers)

        broad_data = serper_search_raw(
            f"{item_name} perfume fragrance EDP EDT ml",
            num=5
        )
        broad_results = parse_serper_results(broad_data)
        trusted_broad = [r for r in broad_results if r["trust_score"] >= 7]

        if trusted_broad:
            log.info(f"  ✓ Found {len(trusted_broad)} results from broad trusted search")
            all_results.extend(trusted_broad)

    if not all_results:
        log.warning(f"  No trusted sources found — including all results for manual review")
        for query in [f"{item_name} perfume", f"{item_name} fragrance"]:
            fallback_data = serper_search_raw(query, num=3)
            all_results.extend(parse_serper_results(fallback_data))

    deduped = deduplicate_results(all_results)
    log.info(f"  Total unique sources: {len(deduped)} | "
             f"Top trust: {max((r['trust_score'] for r in deduped), default=0)}")

    return format_results_for_llm(deduped, item_name)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — AGENT 3: VALIDATOR (Gemini 3.1 Flash Lite)
# See: agents/agent3_validator.md
# ══════════════════════════════════════════════════════════════════════════════

def validate_with_gemini(item: dict, search_result: str) -> dict:
    """Validate a single inventory item using Gemini 3.1 Flash Lite."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=(
            "You are a perfume inventory validation assistant. Always respond with valid JSON only. "
            "No markdown fences, no explanation. Follow naming rules completely and ensure full uppercase output. "
            "If brand/fragrance would represent a different product entirely, flag needs_review=true with "
            "'Brand mismatch — manual review' remarks."
        ),
    )

    prompt = f"""
You are validating a perfume inventory entry against online product data.

NAMING CONVENTION:
{NAMING_RULES}

EMPLOYEE ENTERED:
{json.dumps(item, indent=2)}

SEARCH RESULTS:
{search_result or "No online data found"}

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "corrected_name": "FULL CORRECTED NAME PER CONVENTION",
  "brand": "BRAND NAME",
  "fragrance": "FRAGRANCE NAME ONLY",
  "size_ml": "E.G. 100ML",
  "type": "EDP|EDT|EDC|PARFUM|COLOGNE|BL",
  "gender": "M|W|PH|UNISEX",
  "source_used": "domain name of the source used for validation",
  "remarks": "use remark codes exactly as specified",
  "confidence": "High|Medium|Low",
  "needs_review": false
}}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        validation = json.loads(raw)

        corrected_name = validation.get("corrected_name", "")
        normalized_name = normalize_corrected_name(corrected_name, item)
        if normalized_name and normalized_name != corrected_name:
            validation["corrected_name"] = normalized_name
            if validation.get("remarks") in (None, ""):
                validation["remarks"] = f"Name corrected: {corrected_name} → {normalized_name}"
            elif "Name corrected" not in validation["remarks"]:
                validation["remarks"] += f" | Name corrected: {corrected_name} → {normalized_name}"

        if validation.get("corrected_name"):
            corrected_name = validation["corrected_name"].upper()
            required_type = validation.get("type", "").upper()
            required_size = validation.get("size_ml", "").upper()
            is_giftset = is_giftset_name(corrected_name)

            if required_type and required_type not in corrected_name and not is_giftset:
                corrected_name = f"{corrected_name} {required_type}"
                if validation.get("remarks") in (None, ""):
                    validation["remarks"] = f"Type corrected: missing {required_type}"
                elif f"Type corrected" not in validation["remarks"]:
                    validation["remarks"] += f" | Type corrected: missing {required_type}"
            if required_size and required_size not in corrected_name and not is_giftset:
                corrected_name = f"{corrected_name} {required_size}"
                if validation.get("remarks") in (None, ""):
                    validation["remarks"] = f"Size corrected: missing {required_size}"
                elif f"Size corrected" not in validation["remarks"]:
                    validation["remarks"] += f" | Size corrected: missing {required_size}"
            validation["corrected_name"] = corrected_name.strip()

        if validation.get("brand"):
            validation["brand"] = normalize_short_forms(validation["brand"].upper(), item)
            original_entry = get_item_name(item)
            if not brand_matches_original(validation.get("brand"), original_entry):
                validation["needs_review"] = True
                existing = validation.get("remarks", "")
                bm = "Brand mismatch — manual review"
                if existing and bm not in existing:
                    validation["remarks"] = f"{existing} | {bm}"
                elif not existing:
                    validation["remarks"] = bm

        if not validation.get("source_url"):
            first_url = extract_first_url(search_result)
            if first_url:
                validation["source_url"] = first_url
                if not validation.get("source_used"):
                    validation["source_used"] = normalize_source_name(get_domain(first_url))

        if validation.get("source_used"):
            source_used = validation["source_used"].strip()
            if source_used.lower().startswith("http"):
                validation["source_used"] = normalize_source_name(get_domain(source_used))
            else:
                validation["source_used"] = normalize_source_name(source_used)

        return validation

    except json.JSONDecodeError:
        log.warning("  Gemini returned invalid JSON — flagging for review")
        return {
            "corrected_name": get_item_name(item),
            "remarks": "Parse error — manual review",
            "confidence": "Low",
            "needs_review": True,
        }
    except Exception as e:
        log.error(f"  Gemini API error: {e}")
        return {
            "corrected_name": get_item_name(item),
            "remarks": "API error — manual review",
            "confidence": "Low",
            "needs_review": True,
        }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_validation(items: list[dict]) -> list[dict]:
    """Process all items through the validation pipeline with built-in pacing filters."""
    results = []
    total = len(items)

    for i, item in enumerate(items, 1):
        item_name = get_item_name(item)
        search_key = get_item_search_key(item)
        log.info(f"[{i}/{total}] Processing: {item_name}")

        log.info(f"  Searching by GTIN: {search_key}" if search_key and search_key.isdigit() else f"  Searching: {item_name}")
        search_data = search_product(item_name)

        # FIX: Centralized rate limit sleep pacing to strictly maintain ~13 Requests Per Minute
        # This insulates running processes perfectly from hitting the Free Tier 15 RPM ceiling.
        log.info("  ⏳ Rate limit pacing injection: Pausing for 4.5 seconds...")
        time.sleep(4.5)

        # Validate
        validation = validate_with_gemini(item, search_data)
        log.info(f"  → {validation.get('remarks', 'OK')} [{validation.get('confidence', '?')}] via {validation.get('source_used', 'unknown')}")

        results.append({
            "original_entry": item_name,
            "original_data": item,
            **validation,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — AGENT 4: OUTPUT (CSV + Email)
# See: agents/agent4_output.md
# ══════════════════════════════════════════════════════════════════════════════

def results_to_csv(results: list[dict]) -> str:
    """Convert validation results to CSV string, preserving original input fields."""
    if not results:
        return ""

    original_fields = [f for f in list(results[0].get("original_data", {}).keys()) if f and f.strip()]
    extra_fields = ["Corrected Name", "Remarks", "Source Used", "Confidence", "Needs Review"]
    fieldnames = original_fields + extra_fields

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in results:
        original = r.get("original_data", {}) or {}
        row = {k: original.get(k, "") for k in original_fields}

        source_domain = r.get("source_used") or r.get("source_domain") or ""
        source_url = r.get("source_url") or ""
        source_field = ""

        if source_url and not source_domain:
            source_domain = get_domain(source_url)
        elif source_domain and source_domain.lower().startswith("http"):
            source_domain = get_domain(source_domain)

        label = normalize_source_name(source_domain) or normalize_source_name(source_url) or source_url
        if source_url:
            safe_url = source_url.replace('"', '""')
            safe_label = label.replace('"', '""')
            source_field = f'=HYPERLINK("{safe_url}", "{safe_label}")'
        else:
            source_field = label or source_domain

        row.update({
            "Corrected Name": r.get("corrected_name", ""),
            "Remarks":        r.get("remarks", ""),
            "Source Used":    source_field,
            "Confidence":     r.get("confidence", ""),
            "Needs Review":   "YES" if r.get("needs_review") else "NO",
        })
        writer.writerow(row)

    return output.getvalue()


def compute_stats(results: list[dict]) -> dict:
    ok        = [r for r in results if r.get("remarks") == "OK"]
    review    = [r for r in results if r.get("needs_review")]
    corrected = [r for r in results if not r.get("needs_review") and r.get("remarks") != "OK"]
    return {
        "total":         len(results),
        "ok":            len(ok),
        "corrected":     len(corrected),
        "review":        len(review),
        "review_items":  [r["original_entry"] for r in review],
    }


def send_email_with_attachment(to: str, subject: str, body: str, csv_content: str, filename: str):
    """Send email via Gmail SMTP with CSV attachment."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if csv_content:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(csv_content.encode("utf-8"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())

    log.info(f"Email sent to {to}")


def send_results(original_subject: str, original_sender: str, results: list[dict], csv_content: str):
    """Send validation results back via email."""
    stats = compute_stats(results)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"validated_inventory_{date_str}.csv"

    recipients = list({original_sender, NOTIFY_EMAIL} - {""})
    review_list = "\n".join(f"  • {item}" for item in stats["review_items"]) or "  None — all items verified or auto-corrected."

    body = f"""Hi,

The automated perfume inventory validation has completed for this week's new items.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VALIDATION SUMMARY — {date_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total items processed : {stats['total']}
✅ Verified OK        : {stats['ok']}
⚠️  Auto-corrected    : {stats['corrected']}
🔴 Needs manual review: {stats['review']}

Items requiring manual review:
{review_list}

The full validated results are attached as a CSV file.
Please review flagged items and update the inventory system accordingly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Automated by: Perfume Inventory Validator
Powered by: Gemini 3.1 Flash Lite + Serper API
Run time: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}
"""

    subject = f"Re: {original_subject} — Validation Complete ({stats['total']} items)"

    for recipient in recipients:
        try:
            send_email_with_attachment(
                to=recipient,
                subject=subject,
                body=body,
                csv_content=csv_content,
                filename=filename,
            )
        except Exception as e:
            log.error(f"Failed to send email to {recipient}: {e}")


def save_csv_artifact(csv_content: str):
    """Save CSV to disk as a GitHub Actions artifact."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"output/validated_inventory_{date_str}.csv"
    os.makedirs("output", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(csv_content)
    log.info(f"CSV saved to {filename}")
    return filename


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("PERFUME INVENTORY VALIDATOR — STARTING")
    log.info(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    log.info("=" * 60)

    csv_text, subject, sender = fetch_inventory_email()

    if not csv_text:
        log.error("No inventory CSV found. Exiting.")
        try:
            send_email_with_attachment(
                to=NOTIFY_EMAIL,
                subject="⚠️ Inventory Validator — No Email Found",
                body="The automated validator ran but could not find an inventory email with a CSV attachment in your inbox.",
                csv_content="",
                filename="",
            )
        except Exception:
            pass
        return

    items = parse_csv(csv_text)
    if not items:
        log.error("CSV parsed but contained no items. Exiting.")
        return

    results = run_validation(items)
    csv_output = results_to_csv(results)
    artifact_path = save_csv_artifact(csv_output)

    send_results(
        original_subject=subject or "New Inventory Items",
        original_sender=sender or NOTIFY_EMAIL,
        results=results,
        csv_content=csv_output,
    )

    stats = compute_stats(results)
    log.info("=" * 60)
    log.info("VALIDATION COMPLETE")
    log.info(f"  Total     : {stats['total']}")
    log.info(f"  OK        : {stats['ok']}")
    log.info(f"  Corrected : {stats['corrected']}")
    log.info(f"  Review    : {stats['review']}")
    log.info(f"  Output    : {artifact_path}")
    log.info("=" * 60)

    if stats["review"] > 0:
        log.warning(f"{stats['review']} items need manual review — check the email.")


if __name__ == "__main__":
    main()