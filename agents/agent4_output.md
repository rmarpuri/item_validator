# Agent 4 — Output Agent

## Role
Collects all validated results, generates the corrected CSV, computes a summary,
sends results by email, and saves the CSV as a GitHub Actions artifact.

## Responsibility
- Preserve original input columns in the output CSV
- Append validation columns to the right of original columns
- Compute run statistics
- Send summary email with CSV attached
- Save output CSV to disk for GitHub Actions artifact upload

## Output CSV Schema

### Column Order
1. All original input columns (in their original order, values unchanged)
2. `Corrected Name` — validated name per convention (UPPERCASE, correct suffix/format)
3. `Remarks` — audit trail of what was corrected
4. `Source Used` — domain the validation relied on
5. `Confidence` — High / Medium / Low
6. `Needs Review` — YES / NO

### Key Rule
The original employee-entered values are **never modified** in the output CSV.
Only the appended columns contain corrected/validated data.

## Email Summary Format
```
VALIDATION SUMMARY — YYYY-MM-DD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total items processed :  45
✅ Verified OK        :  28
⚠️  Auto-corrected    :  14
🔴 Needs manual review:   3

Items requiring manual review:
  • UNKNOWN BRAND XYZ 50ML
  • ...
```

## Statistics
| Stat | Definition |
|------|-----------|
| total | All items processed |
| ok | `remarks == "OK"` exactly |
| corrected | `needs_review == false` AND `remarks != "OK"` |
| review | `needs_review == true` |

## Error Handling
| Scenario | Action |
|----------|--------|
| Email send fails | Log error, continue |
| CSV write fails | Log error, raise |
| SMTP auth failure | Log error, do not retry |

## Dependencies
- Python standard library: smtplib, email.mime.*, csv, io, os
- Environment: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `NOTIFY_EMAIL`
