# 🧴 Perfume Inventory Validator

Automated perfume product validation using Gemini AI and Serper search. Validate product names, brands, sizes, and types against online sources.

**How it works:**
```
CSV File → Serper Search → Gemini Validation → Validated CSV Output
```

---

## 🚀 Quick Start

### Option 1: Local CLI (Manual)

```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys
export GEMINI_API_KEY="your-key"
export SERPER_API_KEY="your-key"

# Validate CSV
python scripts/test_local.py ~/Downloads/items.csv --max-items 10
```

**Output:** Results saved to `output/test_output.csv`

---

### Option 2: GitHub Actions (Automated)

1. **Create GitHub repo** (https://github.com/new)
2. **Push code:**
   ```bash
   git init
   git remote add origin https://github.com/YOUR_USERNAME/item_validator.git
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

3. **Add GitHub Secrets:**
   - Go to **Settings → Secrets and variables → Actions**
   - Add `GEMINI_API_KEY`
   - Add `SERPER_API_KEY`

4. **Trigger validation:**
   - **Option A:** Push CSV to `data/` folder → Auto-triggers
   - **Option B:** Manual trigger in **Actions** tab
   - **Option C:** Scheduled daily (edit `.github/workflows/validate.yml`)

5. **Get results:**
   - Check **Actions** tab → Artifacts
   - Auto-committed to `output/test_output.csv`
   - Available in **Releases**

---

## 📋 CSV Input Format

Required columns (any naming convention supported):
- **Description/Name/Item** - Product name
- **GTIN/EAN/UPC** - Product barcode (optional, used for search)

Example:
```csv
Description,GTIN,Quantity
CHANEL N°5 EDP 100ML,3145891260504,5
DIOR SAUVAGE EDT 75ML,3348901247205,3
```

---

## 📊 CSV Output Columns

| Column | Example | Notes |
|--------|---------|-------|
| **Description** | (original CSV) | Original input |
| **Corrected Name** | CHANEL N°5 EDP 100ML | Validated & standardized |
| **Brand** | CHANEL | Extracted brand |
| **Fragrance** | N°5 | Fragrance name only |
| **Size (ML)** | 100ML | Standardized size |
| **Type** | EDP | Eau de Parfum |
| **Gender** | W | M/W/Unisex |
| **Source Used** | Jomashop | Source of validation |
| **Confidence** | High/Medium/Low | Validation confidence |
| **Remarks** | Name corrected | What changed |
| **Needs Review** | YES/NO | Manual review flag |

---

## ⚙️ Configuration

### Naming Rules
Edit `config/naming_rules.json` to customize:
- Brand abbreviations (D&G, S FERRAGAMO, etc.)
- Fragrance type standards
- Gender markers
- Product categories

### Environment Variables
```bash
export GEMINI_API_KEY="..."      # Gemini API key
export SERPER_API_KEY="..."      # Serper search API key
```

Or create `.env` file:
```
GEMINI_API_KEY=...
SERPER_API_KEY=...
```

---

## 🔧 Project Structure

```
item_validator/
├── .github/
│   └── workflows/
│       └── validate.yml          ← GitHub Actions workflow
├── src/
│   └── validator.py              ← Core validation engine
├── scripts/
│   └── test_local.py             ← CLI test runner
├── config/
│   └── naming_rules.json         ← Naming conventions
├── data/                         ← CSV input directory
│   └── items.csv                 ← Your CSV files
├── output/                       ← Results directory
│   └── test_output.csv           ← Validated results
├── agents/                       ← Agent documentation
├── requirements.txt
├── .gitignore
├── .env                          ← Local only (not committed)
└── README.md
```

---

## 📖 Usage Examples

### Validate Single File Locally
```bash
python scripts/test_local.py ~/Downloads/items.csv
```

### Limit to 10 Items (Preview)
```bash
python scripts/test_local.py ~/Downloads/items.csv --max-items 10
```

### Check Validation Output
```bash
head -5 output/test_output.csv
# View results in Excel
open output/test_output.csv
```

### Push to GitHub for Automated Processing
```bash
# Copy CSV to data folder
cp ~/Downloads/items.csv data/items.csv

# Commit and push
git add data/items.csv
git commit -m "Validate new items"
git push origin main

# Check GitHub Actions → Results auto-committed
```

---

## 🔍 How It Works

### Step 1: Search (Serper API)
- Searches by GTIN (if available) or product name
- Returns results from trusted sources:
  - Jomashop ⭐⭐⭐
  - Sephora ⭐⭐⭐
  - Fragrantica ⭐⭐⭐
  - FragranceNet ⭐⭐
  - Other retailers ⭐

### Step 2: Validate (Gemini AI)
- Analyzes search results
- Extracts standardized data
- Cross-references multiple sources
- Flags items needing manual review
- Generates confidence scores

### Step 3: Output
- Generates CSV with validated data
- Hyperlinks to source URLs
- Flags low-confidence items
- Ready for import to WMS

---

## 🎯 Validation Confidence Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **High** | Multiple trusted sources agree | Auto-accept |
| **Medium** | Some sources conflict | Review recommended |
| **Low** | Only unknown sources found | Manual review required |

Items flagged "Needs Review: YES" should be checked before import.

---

## 🚨 Troubleshooting

### "API key not found"
```bash
# Check environment variables
echo $GEMINI_API_KEY
echo $SERPER_API_KEY

# If empty, set them
export GEMINI_API_KEY="your-key"
export SERPER_API_KEY="your-key"

# Or create .env file
echo "GEMINI_API_KEY=your-key" > .env
echo "SERPER_API_KEY=your-key" >> .env
```

### GitHub Actions Workflow Fails
1. Go to **Actions** tab → Failed run
2. Expand logs
3. Check for:
   - Missing API secrets
   - CSV file not found (must be in `data/` folder)
   - API quota exceeded

### CSV Not Processing
- Ensure file is at `data/items.csv`
- Verify CSV has proper headers
- Check file is valid UTF-8 encoding

### Slow Processing
- Large files (100+ items) may take 3-5 minutes
- Check API rate limits at Gemini/Serper dashboards
- Use `--max-items` to process in batches

---

## 📊 Performance

| File Size | Estimated Time |
|-----------|-----------------|
| 1-10 items | 30-60 seconds |
| 10-50 items | 1-2 minutes |
| 50-100 items | 2-3 minutes |
| 100+ items | 3-5+ minutes |

**Tips:**
- Start with small test files
- Monitor API quotas
- Use Preview mode for testing

---

## 🔐 Security

- ✅ API keys stored as GitHub Secrets (encrypted)
- ✅ Never committed to repository
- ✅ Use `.env` locally (in `.gitignore`)
- ✅ Regenerate keys if accidentally exposed

---

## 📝 API Keys

### Gemini API
1. Visit https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy key
4. Add to GitHub Secrets: `GEMINI_API_KEY`

**Free tier:** 1,500 requests/day

### Serper API
1. Visit https://serper.dev/signup
2. Sign up and verify email
3. Go to Dashboard → API Key
4. Copy key
5. Add to GitHub Secrets: `SERPER_API_KEY`

**Free tier:** 100 searches/month

---

## 📚 Documentation

- **[GitHub Actions Setup](GITHUB_ACTIONS_SETUP.md)** - Detailed CI/CD guide
- **[Naming Rules](config/naming_rules.json)** - Customization options
- **[Agent Instructions](agents/)** - AI validation rules

---

## 🤝 Contributing

To improve validation:
1. Edit `config/naming_rules.json` for naming standards
2. Edit `agents/agent3_validator.md` for validation rules
3. Test locally: `python scripts/test_local.py`
4. Push changes to trigger GitHub Actions

---

## 📄 License

MIT

---

## Support

For issues:
1. Check **Troubleshooting** section above
2. Review GitHub Actions logs
3. Verify API quotas
4. Check `.gitignore` includes `.env`

---

**Ready to validate?**

```bash
# Local: python scripts/test_local.py data/items.csv
# GitHub: Push CSV to data/ folder & watch Actions tab
```
