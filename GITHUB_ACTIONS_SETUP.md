# GitHub Actions Deployment Guide

## Setup Steps

### 1. Add API Keys as Secrets
Go to your GitHub repo → **Settings → Secrets and variables → Actions**

Click **New repository secret** and add:

- **Name:** `GEMINI_API_KEY`  
  **Value:** Your Gemini API key from `https://aistudio.google.com/app/apikey`

- **Name:** `SERPER_API_KEY`  
  **Value:** Your Serper API key from `https://serper.dev/dashboard`

### 2. Create CSV Input Directory
```bash
mkdir -p data
# Place your CSV files here (e.g., data/items.csv)
```

### 3. Push to GitHub
```bash
git add .github/workflows/validate.yml
git add data/ requirements.txt src/
git commit -m "Add GitHub Actions validator workflow"
git push origin main
```

---

## Usage

### Option A: Manual Trigger (via GitHub UI)
1. Go to **Actions** tab
2. Select **"Perfume Validator"** workflow
3. Click **Run workflow**
4. Enter CSV path (default: `data/items.csv`)
5. Click **Run workflow**

### Option B: Auto-Trigger
Push any `.csv` file to `data/` folder:
```bash
cp ~/Downloads/ItemList_Friday.CSV data/items.csv
git add data/items.csv
git commit -m "Validate new items"
git push
```
The workflow runs automatically.

### Option C: Programmatic Trigger
```bash
curl -X POST https://api.github.com/repos/YOUR_USER/YOUR_REPO/actions/workflows/validate.yml/dispatches \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+raw" \
  -d '{
    "ref": "main",
    "inputs": {
      "csv_file": "data/items.csv",
      "max_items": "50"
    }
  }'
```

---

## Outputs

### Results Location
- **Artifacts:** `Actions` → Run → `validation-results`  
  (CSV file available for 30 days)

- **GitHub Releases:** Each successful push creates a release with results

- **Repository:** Results committed back to `output/test_output.csv`

### View Results
1. Go to **Actions** → Run name
2. Scroll to **Artifacts** section
3. Download `validation-results` zip file

---

## Environment Variables

The workflow sets these automatically from secrets:
- `GEMINI_API_KEY` → Used by Gemini API
- `SERPER_API_KEY` → Used by Serper search

No need to add to `.env` file; GitHub Actions handles it.

---

## Monitoring

### Check Status
- **Actions tab** → See all runs (green ✅ = success, red ❌ = failed)
- **Click run** → View detailed logs

### Notifications
- GitHub notifies on failures (if enabled in settings)
- Check **Releases** page for successful run summaries

---

## Customization

### Run Only on Specific Schedule
Edit `.github/workflows/validate.yml`, add schedule:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

### Process All Items (No Limit)
Manual trigger → leave `max_items` empty (default 0 = all)

### Change Output Location
Edit workflow → change `path: output/test_output.csv` to desired location

### Skip Auto-Commit
Remove this step if you prefer to review before committing:
```yaml
- name: Commit results back to repo
```

---

## Troubleshooting

### Workflow not appearing
- Ensure file is at `.github/workflows/validate.yml`
- Commit and push the file
- Refresh Actions tab

### "API key not found" error
- Check **Settings → Secrets** for both keys
- Verify secret names exactly match: `GEMINI_API_KEY`, `SERPER_API_KEY`
- Regenerate keys if uncertain

### Python module not found
- Requirements.txt must be in project root
- Verify it has all dependencies: `google-generativeai`, `requests`, `python-dotenv`

### CSV file not found
- Default path: `data/items.csv`
- If using manual trigger, specify correct path in input
- Ensure CSV exists in repo before running

---

## Cost Considerations

- **GitHub Actions:** Free tier includes 2,000 minutes/month (unlimited for public repos)
- **Gemini API:** Free with quota limits
- **Serper API:** Free tier has limits (check your dashboard)

For high volume, consider:
- Scheduling off-peak times
- Batch processing (split large CSVs)
- Upgrading API plans
