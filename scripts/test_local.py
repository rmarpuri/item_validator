"""
Local test script — runs the validator on a sample CSV
without needing a real Gmail inbox.

Usage:
  python scripts/test_local.py

Set your API keys in .env or export them before running:
  export ANTHROPIC_API_KEY=sk-ant-...
  export SERPER_API_KEY=abc123...
"""

import os
import sys
import json
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

def run_test():
    from src.validator import (
        parse_csv, search_product, validate_with_claude,
        results_to_csv, compute_stats, get_item_name
    )

    print("=" * 60)
    print("PERFUME VALIDATOR — LOCAL TEST")
    print("=" * 60)

    # Check env vars
    missing = []
    for key in ["ANTHROPIC_API_KEY", "SERPER_API_KEY"]:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("Export them before running this test.\n")
        sys.exit(1)

    # Parse
    items = parse_csv(SAMPLE_CSV)
    print(f"\n📋 Found {len(items)} test items\n")

    results = []
    for i, item in enumerate(items, 1):
        name = get_item_name(item)
        print(f"[{i}/{len(items)}] {name}")

        search = search_product(name)
        print(f"  🔍 Search: {search[:80].strip()}...")

        validation = validate_with_claude(item, search)
        print(f"  ✅ Corrected: {validation.get('corrected_name', '')}")
        print(f"  📝 Remarks:  {validation.get('remarks', '')}")
        print(f"  🎯 Confidence: {validation.get('confidence', '')}")
        print()

        results.append({"original_entry": name, **validation})

        import time; time.sleep(0.5)

    # Output
    stats = compute_stats(results)
    csv_out = results_to_csv(results)

    os.makedirs("output", exist_ok=True)
    with open("output/test_output.csv", "w") as f:
        f.write(csv_out)

    print("=" * 60)
    print("TEST COMPLETE")
    print(f"  Total     : {stats['total']}")
    print(f"  OK        : {stats['ok']}")
    print(f"  Corrected : {stats['corrected']}")
    print(f"  Review    : {stats['review']}")
    print(f"  Output    : output/test_output.csv")
    print("=" * 60)

    if stats["review_items"]:
        print("\nItems needing manual review:")
        for item in stats["review_items"]:
            print(f"  • {item}")


if __name__ == "__main__":
    run_test()
