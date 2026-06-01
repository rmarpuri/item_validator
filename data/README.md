# Example setup for GitHub Actions data directory

## Directory Structure
```
item_validator/
├── .github/
│   └── workflows/
│       └── validate.yml          # ← The workflow file
├── data/
│   ├── items.csv                 # ← Input CSVs go here
│   └── items_batch2.csv
├── output/
│   └── test_output.csv           # ← Results written here
├── src/
│   └── validator.py
├── scripts/
│   └── test_local.py
├── config/
│   └── naming_rules.json
├── requirements.txt
├── .env                          # ← Local only (not in GitHub)
├── .gitignore
└── README.md
```

## Setup Instructions

### 1. Create data directory locally
```bash
mkdir -p data
```

### 2. Add sample CSV
```bash
# Copy your CSV file to data directory
cp ~/Downloads/ItemList_Friday.CSV data/items.csv

# Or create a simple test file
cat > data/items.csv << 'EOF'
Name,Quantity,Type,Size
Chanel Bleu,3,edp,100
Dior Sauvage,5,EDT,75
EOF
```

### 3. Commit structure
```bash
git add data/
git commit -m "Add data directory structure"
git push
```

### 4. Add GitHub Secrets
Go to: https://github.com/YOUR_USERNAME/item_validator/settings/secrets/actions

Add:
- `GEMINI_API_KEY` = your key
- `SERPER_API_KEY` = your key

### 5. Trigger workflow
Option A: GitHub UI → Actions → Run workflow  
Option B: Push CSV file to data/ → Auto-triggers

## Notes

- `.env` file should be in `.gitignore` (don't commit API keys to repo)
- `output/test_output.csv` will be auto-committed on successful run
- Workflow artifacts persist for 30 days in Actions tab
