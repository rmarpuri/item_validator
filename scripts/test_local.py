"""
Local test script — runs the validator on a sample CSV
without needing a real Gmail inbox.

Usage:
  python scripts/test_local.py

Set your API keys in .env or export them before running:
  export GEMINI_API_KEY=AIza...
  export SERPER_API_KEY=abc123...
"""

import argparse
import os
import sys
import json
from dotenv import load_dotenv

# Load .env file from project root before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Sample test data — edit to match your real inventory columns ──────────────
SAMPLE_CSV = """Name,Quantity,Type,Size,Gender
Chanel Bleu edp,3,edp,100,
dior sauvage edt 75ml,5,EDT,75,men
CHANEL NO 5 EDP,2,edp,200ml,women
YSL Black Opium 90,1,edp,90,
versace eros EDT,4,edt,100ml,Men
Jo Malone Peony & Blush Suede,2,,100,women
Creed Aventus 50,1,edp,50,Men
"""

def run_test(csv_path=None, max_items=10):
    from src.validator import (
        parse_csv, search_product, validate_with_gemini,
        results_to_csv, compute_stats, get_item_name
    )

    print("=" * 60)
    print("PERFUME VALIDATOR — LOCAL TEST")
    print("=" * 60)

    # Check env vars
    missing = []
    for key in ["GEMINI_API_KEY", "SERPER_API_KEY"]:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("Export them before running this test.\n")
        sys.exit(1)

    if csv_path:
        if not os.path.isfile(csv_path):
            print(f"\n❌ CSV file not found: {csv_path}\n")
            sys.exit(1)
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_text = f.read()
        print(f"\nUsing input file: {csv_path}\n")
    else:
        csv_text = SAMPLE_CSV
        print("\nUsing built-in sample data\n")

    # Parse
    items = parse_csv(csv_text)
    if max_items and len(items) > max_items:
        print(f"📋 Found {len(items)} test items, validating top {max_items} only\n")
        items = items[:max_items]
    else:
        print(f"📋 Found {len(items)} test items\n")

    results = []
    for i, item in enumerate(items, 1):
        name = get_item_name(item)
        print(f"[{i}/{len(items)}] {name}")

        search = search_product(item)
        print(f"  🔍 Search: {search[:80].strip()}...")

        validation = validate_with_gemini(item, search)
        print(f"  ✅ Corrected: {validation.get('corrected_name', '')}")
        print(f"  📝 Remarks:  {validation.get('remarks', '')}")
        print(f"  🎯 Confidence: {validation.get('confidence', '')}")
        print()

        results.append({
            "original_entry": name,
            "original_data": item,
            **validation,
        })

        import time; time.sleep(0.5)

    # Output
    stats = compute_stats(results)
    
    csv_out = results_to_csv(results)

    os.makedirs("output", exist_ok=True)
    with open("output/test_output.csv", "w") as f:
        f.write(csv_out)

    print("=" * 60)
    print("TEST COMPLETE")
    print(f"  Total              : {stats['total']}")
    print(f"  OK                 : {stats['ok']}")
    print(f"  Corrected          : {stats['corrected']}")
    print(f"  Items to review    : {stats['review']}")
    print(f"  Output CSV         : output/test_output.csv")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run local perfume inventory validation against a CSV file."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        help="Optional path to a local CSV file to validate. If omitted, sample test data is used.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Validate only the first N items from the CSV. Default is 10.",
    )
    args = parser.parse_args()
    run_test(args.csv_file, max_items=args.max_items)