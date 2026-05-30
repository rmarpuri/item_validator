# 🧴 Perfume Inventory Validator

Automated AI agent that runs every Friday to validate new perfume inventory entries from Gmail.

**Pipeline:**
```
Gmail Inbox → CSV Attachment → Serper Search (Jomashop) → Claude Haiku Validation → Email Reply + CSV Output
```

---

## 📁 Project Structure

```
perfume-validator/
├── .github/
│   └── workflows/
│       └── friday-validator.yml   ← GitHub Actions scheduler
├── src/
│   └── validator.py               ← Core agent logic
├── scripts/
│   └── test_local.py              ← Local test runner
├── config/
│   └── naming_rules.json          ← Edit naming convention here
├── output/                        ← Generated CSVs (gitignored)
├── requirements.txt
└── README.md
```

---

## ⚙️ One-Time Setup

### Step 1 — Create GitHub Repository

```bash
git init perfume-validator
cd perfume-validator
# Copy all these files in
git add .
git commit -m "Initial setup"
git remote add origin https://github.com/YOUR_USERNAME/perfume-validator.git
git push -u origin main
```

### Step 2 — Get Your API Keys

| Key | Where to get it | Free tier |
|-----|----------------|-----------|
| `ANTHROPIC_API_KEY` | console.anthropic.com | Pay per use (~$1-2/month) |
| `SERPER_API_KEY` | serper.dev | 100 searches/day free |
| `GMAIL_APP_PASSWORD` | See below | Free |
| `GMAIL_USER` | Your Gmail address | Free |
| `NOTIFY_EMAIL` | Email to receive results | — |

### Step 3 — Create Gmail App Password

> Required because Google blocks direct password login for scripts.

1. Go to **myaccount.google.com**
2. Click **Security** → **2-Step Verification** (enable if not already)
3. Scroll down → **App passwords**
4. Select **Mail** + **Other (custom name)** → name it "Inventory Validator"
5. Copy the 16-character password shown — this is your `GMAIL_APP_PASSWORD`

### Step 4 — Add Secrets to GitHub

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret Name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` |
| `SERPER_API_KEY` | Your Serper key |
| `GMAIL_USER` | `yourname@gmail.com` |
| `GMAIL_APP_PASSWORD` | The 16-char app password |
| `NOTIFY_EMAIL` | Email to receive results |

### Step 5 — Enable Gmail IMAP

1. Open Gmail → **Settings** (gear icon) → **See all settings**
2. Click **Forwarding and POP/IMAP** tab
3. Under IMAP Access → **Enable IMAP**
4. Save changes

---

## 🚀 Running the Validator

### Automatic (Every Friday 9 AM UTC)
Just push to GitHub — the workflow runs automatically every Friday.

To change the time, edit `.github/workflows/friday-validator.yml`:
```yaml
- cron: "0 9 * * 5"   # 9:00 AM UTC every Friday
- cron: "0 2 * * 5"   # 2:00 AM UTC (= 10 AM SGT)
- cron: "0 1 * * 5"   # 1:00 AM UTC (= 9 AM SGT)
```

[Cron time converter](https://crontab.guru/)

### Manual Trigger
1. Go to GitHub repo → **Actions** tab
2. Click **Perfume Inventory Validator**
3. Click **Run workflow** → **Run workflow**

### Local Test (before deploying)
```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export SERPER_API_KEY=abc123...

# Run test with sample data (no Gmail needed)
python scripts/test_local.py

# Check output
cat output/test_output.csv
```

---

## 📧 How the Email Trigger Works

The validator searches your Gmail inbox for the most recent email with any of these keywords in the subject:
- `inventory`
- `new items`
- `fragrance`
- `perfume`
- `stock`
- `weekly items`

The email must have a **CSV or Excel (.xlsx/.xls) attachment**.

Edit keywords in `config/naming_rules.json` under `email_search_keywords`.

---

## 📊 Output

### Validated CSV columns:
| Column | Description |
|--------|-------------|
| Original Entry | What the employee typed |
| Corrected Name | Fixed name per convention |
| Brand | Brand name |
| Fragrance | Fragrance name |
| Size | Size in ml |
| Type | EDP / EDT / EDC / etc. |
| Gender | Men / Women / Unisex |
| Remarks | What was changed (or OK) |
| Confidence | High / Medium / Low |
| Needs Review | YES / NO |

### Email summary sent every Friday:
```
VALIDATION SUMMARY — 2026-01-10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total items processed : 45
✅ Verified OK        : 28
⚠️  Auto-corrected    : 14
🔴 Needs manual review:  3

Items requiring manual review:
  • Unknown Brand XYZ 50ml
  • ...
```

---

## 🔧 Customizing Naming Rules

Edit `config/naming_rules.json` — no code changes needed:

```json
{
  "naming_format": "[Brand] [Fragrance Name] [Size]ml [Type]",
  "valid_types": ["EDP", "EDT", "EDC", "Parfum", "Cologne"],
  "common_corrections": {
    "edp": "EDP",
    "eau de parfum": "EDP"
  }
}
```

---

## 💰 Monthly Cost

| Service | Cost |
|---------|------|
| Claude Haiku (100 items/week) | ~$1–2/month |
| Serper API (free tier) | $0 |
| GitHub Actions | $0 |
| Gmail IMAP | $0 |
| **Total** | **~$1–2/month** |

---

## 🐛 Troubleshooting

**"No inventory email found"**
→ Check Gmail IMAP is enabled
→ Check subject contains one of the keywords
→ Make sure attachment is .csv or .xlsx

**"Serper API error: 401"**
→ Check `SERPER_API_KEY` secret is correct

**"Claude API error"**
→ Check `ANTHROPIC_API_KEY` secret
→ Check your Anthropic account has credits

**"Gmail login failed"**
→ Use App Password, not your normal Gmail password
→ Ensure 2FA is enabled on Google account

**Items always show "Low confidence"**
→ The product may not be on Jomashop
→ Try broadening the search in `config/naming_rules.json`
