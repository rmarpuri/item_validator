# Agent Orchestrator — System Overview

## System Architecture

This system is a 4-agent pipeline that runs every Friday automatically via GitHub Actions.
Each agent has a single, well-defined responsibility. They are orchestrated sequentially
by `src/validator.py`.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS SCHEDULER                         │
│              Triggers every Friday 9:00 AM UTC                      │
│                   (cron: "0 9 * * 5")                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AGENT 1 — EMAIL READER                                             │
│  Tool    : Gmail IMAP (imaplib)                                     │
│  Input   : Gmail inbox                                              │
│  Output  : Raw CSV text + email subject + sender address            │
│  File    : agents/agent1_email_reader.md                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  csv_text, subject, sender
                               ▼
                    ┌──────────────────────┐
                    │   PARSE CSV          │
                    │   (csv.DictReader)   │
                    │   Output: list[dict] │
                    └──────────┬───────────┘
                               │  items[]
                               ▼
              ┌────────────────────────────────────┐
              │   FOR EACH ITEM (loop)             │
              │                                    │
              │  ┌─────────────────────────────┐   │
              │  │  AGENT 2 — SMART SEARCH     │   │
              │  │  Tool   : Serper API        │   │
              │  │  Input  : item_name string  │   │
              │  │  Output : ranked search     │   │
              │  │           results with      │   │
              │  │           trust scores      │   │
              │  │  File   : agent2_smart_     │   │
              │  │           search.md         │   │
              │  └──────────────┬──────────────┘   │
              │                 │  search_result    │
              │                 ▼                   │
              │  ┌─────────────────────────────┐   │
              │  │  AGENT 3 — VALIDATOR        │   │
              │  │  Model  : Gemini 3.1 Flash Lite  │   │
              │  │  Input  : item + search     │   │
              │  │           results           │   │
              │  │  Output : corrected JSON    │   │
              │  │  File   : agent3_validator  │   │
              │  │           .md               │   │
              │  └──────────────┬──────────────┘   │
              │                 │  validation dict  │
              └─────────────────┼──────────────────┘
                                │  results[]
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AGENT 4 — OUTPUT                                                   │
│  Tool    : Gmail SMTP + CSV writer                                  │
│  Input   : results[] + original subject + sender                   │
│  Output  : Validated CSV file + Email reply + GitHub artifact       │
│  File    : agents/agent4_output.md                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Summary Table

| Agent | Name | Tool/Model | Input | Output | Cost |
|-------|------|-----------|-------|--------|------|
| 1 | Email Reader | Gmail IMAP | Gmail inbox | CSV text | Free |
| 2 | Smart Search | Serper API | Item name | Ranked results | Free (100/day) |
| 3 | Validator | Gemini 3.1 Flash Lite | Item + search data | Corrected JSON | Free (project quota) |
| 4 | Output | Gmail SMTP | All results | CSV + Email | Free |

**Total cost: $0/month**

---

## Data Flow

```
Gmail Email (attachment)
    │
    ├─ [Agent 1] → csv_text: "Name,Qty,Type\nChanel Bleu edp,3,100\n..."
    │
    ├─ [Parse]   → items: [{"Name": "Chanel Bleu edp", "Qty": "3", ...}, ...]
    │
    ├─ [Agent 2] → search_result: "[1] Chanel Bleu de Chanel EDP 100ml
    │                               Source: jomashop.com [★★★ HIGHLY TRUSTED]
    │                               URL: https://jomashop.com/..."
    │
    ├─ [Agent 3] → validation: {
    │                "corrected_name": "Chanel Bleu de Chanel 100ml EDP",
    │                "brand": "Chanel",
    │                "type": "EDP",
    │                "size_ml": "100ml",
    │                "gender": "Men",
    │                "source_used": "jomashop.com",
    │                "remarks": "Name corrected",
    │                "confidence": "High",
    │                "needs_review": false
    │              }
    │
    └─ [Agent 4] → validated_inventory_2026-05-30.csv (emailed + artifact)
```

---

## Environment Variables Required

| Variable | Used By | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | Agent 3 | Google AI Studio API key (free) |
| `SERPER_API_KEY` | Agent 2 | Serper.dev API key (free, 100/day) |
| `GMAIL_USER` | Agent 1, 4 | Gmail address (e.g. company@gmail.com) |
| `GMAIL_APP_PASSWORD` | Agent 1, 4 | Gmail App Password (16 chars) |
| `NOTIFY_EMAIL` | Agent 4 | Who receives the result email |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/naming_rules.json` | Edit naming convention, remark codes, trusted keywords |
| `agents/agent1_email_reader.md` | Agent 1 instructions and error handling |
| `agents/agent2_smart_search.md` | Agent 2 trust scores, search strategy |
| `agents/agent3_validator.md` | Agent 3 prompt logic, confidence rules |
| `agents/agent4_output.md` | Agent 4 email format, CSV schema |

---

## Weekly Run Timeline (Fridays)

```
09:00 UTC — GitHub Actions triggers the workflow
09:00:05  — Agent 1: Connect to Gmail, find latest inventory email
09:00:10  — Agent 1: Extract and decode CSV attachment
09:00:11  — Parse CSV → n items loaded
09:00:12  — Loop begins
            Per item (~2–3 seconds each):
              Agent 2: Serper search (Pass 1: Jomashop)
              Agent 2: Serper search (Pass 2+3 if needed)
              Agent 3: Gemini validates → JSON result
09:05:00  — (approx, for 100 items) Loop complete
09:05:01  — Agent 4: Generate CSV
09:05:02  — Agent 4: Send email reply to sender
09:05:03  — Agent 4: Send email to NOTIFY_EMAIL
09:05:04  — Agent 4: Save CSV to output/
09:05:05  — GitHub Actions uploads artifact
09:05:10  — Workflow complete ✅
```

---

## Adding a New Agent

To extend the pipeline (e.g. Agent 5 — write to Google Sheets):
1. Create `agents/agent5_sheets_writer.md` with full instructions
2. Add the function to `src/validator.py`
3. Call it from `main()` after Agent 4
4. Add any new secrets to GitHub Secrets and `.env`
