# Agent 1 — Email Reader

## Role
Connects to the company Gmail inbox via IMAP every Friday and retrieves
the latest inventory email that contains a new items list as an attachment.

## Responsibility
- Connect securely to Gmail using IMAP + App Password
- Search the inbox for emails matching inventory-related subject keywords
- Identify and extract the most recent matching email
- Parse the attachment — supports CSV, XLSX, XLS formats
- Fall back to reading inline CSV from the email body if no attachment found
- Return raw CSV text to the orchestrator

## Input
- Gmail credentials (GMAIL_USER, GMAIL_APP_PASSWORD) from environment
- Subject search keywords defined in config/naming_rules.json

## Output
Returns a tuple: (csv_text, subject, sender)
- csv_text  : Raw CSV string of new inventory items
- subject   : Original email subject (used in reply)
- sender    : Sender email address (used to reply back)
- Returns (None, None, None) if no matching email is found

## Search Keywords (from config)
Searches Gmail inbox for subject lines containing any of:
  - "inventory"
  - "new items"
  - "fragrance"
  - "perfume"
  - "stock"
  - "weekly items"

## Supported Attachment Formats
| Format | Handling |
|--------|----------|
| .csv   | Decoded directly as UTF-8 text |
| .xlsx  | Converted to CSV via openpyxl |
| .xls   | Converted to CSV via openpyxl |
| inline | Detected if email body contains comma-separated data with 2+ lines |

## Error Handling
| Scenario | Action |
|----------|--------|
| No matching email found | Log warning, return (None, None, None), notify via email |
| Email found but no attachment | Log warning, return (None, subject, sender) |
| IMAP connection failure | Raise exception, GitHub Actions marks run as failed |
| Attachment decode error | Log error, skip attachment, try body fallback |

## Security Notes
- Uses Gmail App Password (not account password) — revocable at any time
- Credentials stored only in GitHub Secrets / local .env — never in code
- IMAP SSL on port 993 — all traffic encrypted
- Read-only operation — agent never deletes or modifies emails

## Dependencies
- Python standard library: imaplib, email, email.header
- openpyxl (for Excel conversion)
- Environment vars: GMAIL_USER, GMAIL_APP_PASSWORD
