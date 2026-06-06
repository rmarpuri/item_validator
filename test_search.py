import sys
import json
from src.validator_1 import execute_search_query, deduplicate_results, format_results_for_llm
from dotenv import load_dotenv

load_dotenv()

query = "D&G LIGHT BLUE EDT 200ML 8057971188208 perfume"
print("Ebay search:")
ebay = [r for r in execute_search_query(f"site:ebay.com {query}") if r["trust_score"] == 10]
print(json.dumps(ebay, indent=2))
