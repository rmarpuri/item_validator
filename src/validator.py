"""
Perfume Inventory Validator — Core Agent
Runs every Friday via GitHub Actions.
Pipeline: Gmail → Parse CSV → Serper Search → Claude Haiku Validate → Email Reply + CSV output
"""

import os
import json
import time
import base64
import csv
import io
import logging
from datetime import datetime
from typing import Optional

import anthropic
import requests

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY    = os.environ["SERPER_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]          # your.email@company.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"] # Gmail App Password (not login password)
NOTIFY_EMAIL      = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)

# ── Naming convention rules ────────────────────────────────────────────────────
NAMING_RULES = """
PERFUME INVENTORY NAMING CONVENTION:
- Format: [Brand] [Fragrance Name] [Size]ml [Type]
- Type must be one of: EDP, EDT, EDC, Parfum, Cologne
- Size must be numeric followed by ml (e.g. 100ml, 50ml, 200ml)
- Gender: Men / Women / Unisex
- Brand name must be properly capitalized (e.g. "Chanel" not "chanel")
- Common corrections: "edp"→"EDP", "edt"→"EDT", "eau de parfum"→"EDP"

VALIDATION TASKS:
1. Check if name follows the format above
2. Verify EDP vs EDT is correct based on product data
3. Verify size/quantity in ml
4. Determine gender (Men/Women/Unisex)
5. Flag any discrepancies with clear remarks

REMARK CODES (use these exactly):
- "OK" — entry is correct
- "Name corrected" — brand/fragrance name fixed
- "Type corrected: X→Y" — e.g. "Type corrected: EDT→EDP"
- "Size corrected: Xml→Yml" — size was wrong
- "Gender added" — gender was missing
- "Not found — manual review" — could not verify
- Combine with " | " if multiple issues
"""

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — FETCH EMAIL WITH ATTACHMENT
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
# STEP 2 — PARSE CSV
# ══════════════════════════════════════════════════════════════════════════════

def parse_csv(csv_text: str) -> list[dict]:
    """Parse CSV text into list of dicts."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    items = [row for row in reader]
    log.info(f"Parsed {len(items)} items from CSV")
    return items


def get_item_name(item: dict) -> str:
    """Extract the product name from a CSV row regardless of column naming."""
    for key in item:
        if any(k in key.lower() for k in ["name", "product", "item", "description", "fragrance"]):
            val = item[key].strip()
            if val:
                return val
    # Fallback: first non-empty value
    return next((v.strip() for v in item.values() if v.strip()), "Unknown Item")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SERPER SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def serper_search(query: str) -> str:
    """Search Google via Serper API. Returns structured text summary."""
    try:
        res = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 3},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()

        summary_parts = []

        # Knowledge graph — richest source
        kg = data.get("knowledgeGraph", {})
        if kg.get("title"):
            summary_parts.append(f"KNOWLEDGE GRAPH:")
            summary_parts.append(f"  Title: {kg['title']}")
            if kg.get("type"):
                summary_parts.append(f"  Type: {kg['type']}")
            if kg.get("description"):
                summary_parts.append(f"  Description: {kg['description']}")
            for k, v in (kg.get("attributes") or {}).items():
                summary_parts.append(f"  {k}: {v}")
            summary_parts.append("")

        # Organic results
        for i, r in enumerate(data.get("organic", [])[:3], 1):
            summary_parts.append(f"[{i}] {r.get('title', '')}")
            summary_parts.append(f"    URL: {r.get('link', '')}")
            summary_parts.append(f"    {r.get('snippet', '')}")
            summary_parts.append("")

        return "\n".join(summary_parts) if summary_parts else "No results found"

    except Exception as e:
        log.warning(f"Serper search error: {e}")
        return f"Search error: {e}"


def search_product(item_name: str) -> str:
    """Search Jomashop first, fall back to broad search."""
    log.info(f"  Searching: {item_name}")

    # Try Jomashop-specific
    result = serper_search(f"site:jomashop.com {item_name}")
    if "No results found" not in result and "Search error" not in result:
        return result

    # Broad fallback
    log.info(f"  Jomashop miss — trying broad search")
    return serper_search(f"{item_name} perfume EDP EDT fragrance ml")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — CLAUDE HAIKU VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_with_claude(item: dict, search_result: str) -> dict:
    """Validate a single inventory item using Claude Haiku."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
You are validating a perfume inventory entry.

NAMING CONVENTION:
{NAMING_RULES}

EMPLOYEE ENTERED:
{json.dumps(item, indent=2)}

PRODUCT DATA FROM SEARCH:
{search_result or "No online data found"}

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "corrected_name": "full corrected name per convention",
  "brand": "brand name",
  "fragrance": "fragrance name only",
  "size_ml": "e.g. 100ml",
  "type": "EDP|EDT|EDC|Parfum|Cologne",
  "gender": "Men|Women|Unisex",
  "remarks": "use remark codes exactly as specified",
  "confidence": "High|Medium|Low",
  "needs_review": false
}}
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system="You are a perfume inventory validation assistant. Always respond with valid JSON only. No markdown fences.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except json.JSONDecodeError:
        log.warning(f"  Claude returned invalid JSON — flagging for review")
        return {
            "corrected_name": get_item_name(item),
            "remarks": "Parse error — manual review",
            "confidence": "Low",
            "needs_review": True,
        }
    except Exception as e:
        log.error(f"  Claude API error: {e}")
        return {
            "corrected_name": get_item_name(item),
            "remarks": f"API error — manual review",
            "confidence": "Low",
            "needs_review": True,
        }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_validation(items: list[dict]) -> list[dict]:
    """Process all items through the validation pipeline."""
    results = []
    total = len(items)

    for i, item in enumerate(items, 1):
        item_name = get_item_name(item)
        log.info(f"[{i}/{total}] Processing: {item_name}")

        # Search
        search_data = search_product(item_name)

        # Validate
        validation = validate_with_claude(item, search_data)
        log.info(f"  → {validation.get('remarks', 'OK')} [{validation.get('confidence', '?')}]")

        results.append({
            "original_entry": item_name,
            "original_data": item,
            **validation,
        })

        # Rate limit buffer — Serper allows 100/day, Claude Haiku is generous
        time.sleep(0.5)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — OUTPUT: CSV + EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def results_to_csv(results: list[dict]) -> str:
    """Convert validation results to CSV string."""
    fieldnames = [
        "Original Entry", "Corrected Name", "Brand", "Fragrance",
        "Size", "Type", "Gender", "Remarks", "Confidence", "Needs Review"
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in results:
        writer.writerow({
            "Original Entry":  r.get("original_entry", ""),
            "Corrected Name":  r.get("corrected_name", ""),
            "Brand":           r.get("brand", ""),
            "Fragrance":       r.get("fragrance", ""),
            "Size":            r.get("size_ml", ""),
            "Type":            r.get("type", ""),
            "Gender":          r.get("gender", ""),
            "Remarks":         r.get("remarks", ""),
            "Confidence":      r.get("confidence", ""),
            "Needs Review":    "YES" if r.get("needs_review") else "NO",
        })

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


def send_email_with_attachment(
    to: str,
    subject: str,
    body: str,
    csv_content: str,
    filename: str,
):
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

    # Attach CSV
    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_content.encode("utf-8"))
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())

    log.info(f"Email sent to {to}")


def send_results(
    original_subject: str,
    original_sender: str,
    results: list[dict],
    csv_content: str,
):
    """Send validation results back via email."""
    stats = compute_stats(results)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"validated_inventory_{date_str}.csv"

    # Determine recipient: reply to sender, also notify main user
    recipients = list({original_sender, NOTIFY_EMAIL} - {""})

    review_list = "\n".join(
        f"  • {item}" for item in stats["review_items"]
    ) or "  None — all items verified or auto-corrected."

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
Powered by: Claude Haiku + Serper API
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

    # ── Step 1: Fetch email ──────────────────────────────────────────────────
    csv_text, subject, sender = fetch_inventory_email()

    if not csv_text:
        log.error("No inventory CSV found. Exiting.")
        # Send a failure notification
        try:
            send_email_with_attachment(
                to=NOTIFY_EMAIL,
                subject="⚠️ Inventory Validator — No Email Found",
                body="The automated validator ran but could not find an inventory email with a CSV attachment in your inbox.\n\nPlease check that the Friday inventory email was received and has a CSV or Excel attachment.",
                csv_content="",
                filename="",
            )
        except Exception:
            pass
        return

    # ── Step 2: Parse CSV ────────────────────────────────────────────────────
    items = parse_csv(csv_text)
    if not items:
        log.error("CSV parsed but contained no items. Exiting.")
        return

    # ── Step 3+4: Search + Validate ──────────────────────────────────────────
    results = run_validation(items)

    # ── Step 5: Generate output CSV ──────────────────────────────────────────
    csv_output = results_to_csv(results)
    artifact_path = save_csv_artifact(csv_output)

    # ── Step 6: Send email ───────────────────────────────────────────────────
    send_results(
        original_subject=subject or "New Inventory Items",
        original_sender=sender or NOTIFY_EMAIL,
        results=results,
        csv_content=csv_output,
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    stats = compute_stats(results)
    log.info("=" * 60)
    log.info("VALIDATION COMPLETE")
    log.info(f"  Total     : {stats['total']}")
    log.info(f"  OK        : {stats['ok']}")
    log.info(f"  Corrected : {stats['corrected']}")
    log.info(f"  Review    : {stats['review']}")
    log.info(f"  Output    : {artifact_path}")
    log.info("=" * 60)

    # Exit with error code if any items need review (alerts GitHub Actions)
    if stats["review"] > 0:
        log.warning(f"{stats['review']} items need manual review — check the email.")


if __name__ == "__main__":
    main()
