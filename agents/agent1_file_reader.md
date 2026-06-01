# Agent 1 — File Reader

## Role
Reads the `items_list.csv` (or `.xlsx` / `.xls`) file provided on demand via the
CLI `--file` argument and returns raw CSV text to the orchestrator.

## Responsibility
- Accept a file path from the CLI `--file` argument
- Validate the file exists and has a supported format
- Read CSV files directly as UTF-8 text
- Convert Excel files to CSV using openpyxl
- Return raw CSV text to the orchestrator for parsing

## Input
- `--file PATH` CLI argument (required)
- Supported formats: `.csv`, `.xlsx`, `.xls`

## Output
Returns raw CSV text string to the orchestrator.

## Supported Formats
| Format | Handling |
|--------|----------|
| .csv   | Read directly as UTF-8 text |
| .xlsx  | Converted to CSV via openpyxl (first sheet used) |
| .xls   | Converted to CSV via openpyxl (first sheet used) |

## Error Handling
| Scenario | Action |
|----------|--------|
| File not found | Log error, exit with code 1 |
| Unsupported format | Log error, exit with code 1 |
| File empty | Log error, exit with code 1 |
| Encoding error | Use UTF-8 with replace mode |

## CLI Usage
```bash
# Basic run
python src/validator.py --file items_list.csv

# With custom output dir
python src/validator.py --file items_list.csv --output-dir ./results

# Skip email, just generate CSV
python src/validator.py --file items_list.csv --no-email

# Override notification email
python src/validator.py --file items_list.csv --notify manager@company.com
```

## Dependencies
- Python standard library: pathlib, csv, io
- openpyxl (for Excel conversion)
