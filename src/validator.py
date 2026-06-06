"""
ENHANCED PERFUME VALIDATOR — Complete Integration
Adds: Brand abbreviations, Gender extraction, Country of origin, Source hyperlinks

KEY FEATURES:
✓ Brand abbreviations (D&G, JPG, CH, etc.)
✓ Gender extracted and included in corrected name
✓ Country of origin extracted and included
✓ Source links with hyperlinks in CSV
✓ Complete audit trail
✓ Strict source-based validation
"""

import os
import json
import re
import time
import base64
import csv
import io
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

import google.generativeai as genai
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
SERPER_API_KEY        = os.environ.get("SERPER_API_KEY", "")
SERPER_API_KEY_BKP    = os.environ.get("SERPER_API_KEY_BKP", "")
BRAVE_API_KEY         = os.environ.get("BRAVE_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX      = os.environ.get("GOOGLE_SEARCH_CX", "")

GMAIL_USER            = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD    = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL          = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)

# ════════════════════════════════════════════════════════════════════════════════
# BRAND ABBREVIATIONS
# ════════════════════════════════════════════════════════════════════════════════

BRAND_ABBREVIATIONS = {
    "DOLCE & GABBANA": "D&G",
    "DOLCE AND GABBANA": "D&G",
    "DOLCE&GABBANA": "D&G",
    "JEAN PAUL GAULTIER": "JPG",
    "CAROLINA HERRERA": "CH",
    "VIKTOR & ROLF": "V&R",
    "VIKTOR AND ROLF": "V&R",
    "MARC JACOBS": "MJ",
    "LANCE ROMANCE": "LR",
}

def apply_brand_abbreviations(brand: str) -> str:
    """Apply brand abbreviations (D&G instead of DOLCE & GABBANA)"""
    if not brand:
        return brand
    
    brand_upper = brand.upper().strip()
    
    for full_name, abbrev in BRAND_ABBREVIATIONS.items():
        if brand_upper == full_name.upper():
            return abbrev
    
    return brand

# ════════════════════════════════════════════════════════════════════════════════
# DATA EXTRACTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def extract_brand(search_result: str) -> Optional[str]:
    """Extract brand name from search result"""
    patterns = [
        r'(?:brand|by)\s*[:\s]+([A-Za-z\s&]+?)(?:\s+(?:perfume|fragrance|eau|edt|edp)|$)',
        r'^([A-Za-z\s&]+?)\s+(?:perfume|fragrance|eau|edt|edp)',
    ]
    for pattern in patterns:
        match = re.search(pattern, search_result, re.IGNORECASE)
        if match:
            brand = match.group(1).strip().upper()
            return apply_brand_abbreviations(brand)
    return None


def extract_type(search_result: str) -> Optional[str]:
    """Extract fragrance type from search result"""
    upper = search_result.upper()
    
    if 'EAU DE PARFUM' in upper or ('PARFUM' in upper and 'EAU' not in upper):
        return 'EDP'
    elif 'EAU DE TOILETTE' in upper:
        return 'EDT'
    elif 'EAU DE COLOGNE' in upper:
        return 'EDC'
    elif 'COLOGNE' in upper and 'EAU DE' not in upper:
        return 'COLOGNE'
    elif 'BODY LOTION' in upper or 'BL' in upper:
        return 'BL'
    elif 'SHAMPOO' in upper or 'HAIR & BODY' in upper or 'H&B' in upper:
        return 'SHAMPOO'
    elif 'BODY WASH' in upper or 'SHOWER GEL' in upper:
        return 'SG'
    elif 'DEODORANT' in upper or 'DEO' in upper:
        return 'DEO'
    elif 'AFTER SHAVE' in upper or 'AS' in upper:
        return 'AS'
    elif re.search(r'\b(EDP|EDT|EDC)\b', upper):
        return re.search(r'\b(EDP|EDT|EDC)\b', upper).group(1)
    
    return None


def extract_gender(search_result: str) -> Optional[str]:
    """Extract gender from search result"""
    upper = search_result.upper()
    
    if re.search(r'\bfor\s+men\b|\bmen\'?s?\b|\bhomme\b', upper):
        return 'M'
    elif re.search(r'\bfor\s+women\b|\bwomen\'?s?\b|\bfemme\b', upper):
        return 'W'
    elif re.search(r'\bunisex\b', upper):
        return 'UNISEX'
    elif re.search(r'\bpour\s+homme\b', upper):
        return 'PH'
    
    return None


def extract_size_ml(search_result: str) -> Optional[str]:
    """Extract size in ML from search result"""
    # Look for ml
    ml_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ml|mL|ML)', search_result)
    if ml_match:
        ml_value = int(float(ml_match.group(1)))
        return f'{ml_value}ML'
    
    # Look for oz and convert
    oz_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:oz|fl\.?oz)', search_result, re.IGNORECASE)
    if oz_match:
        oz_value = float(oz_match.group(1))
        ml_value = int(oz_value * 29.5735)
        return f'{ml_value}ML'
    
    return None


def extract_country(search_result: str) -> Optional[str]:
    """Extract country of origin from search result"""
    patterns = {
        'FR': [r'\bfrance\b', r'\bmade in fr\b', r'\bmade in france\b'],
        'IT': [r'\bitaly\b', r'\bmade in it\b', r'\bmade in italy\b'],
        'US': [r'\busa\b', r'\bunited states\b'],
        'DE': [r'\bgermany\b', r'\bmade in de\b'],
        'GB': [r'\buk\b', r'\benglish\b'],
        'JP': [r'\bjapan\b', r'\bmade in jp\b'],
        'ES': [r'\bspain\b', r'\bmade in es\b'],
        'CH': [r'\bswitzerland\b', r'\bswiss\b'],
    }
    
    upper = search_result.upper()
    for code, patterns_list in patterns.items():
        for pattern in patterns_list:
            if re.search(pattern, upper):
                return code
    
    return None


def extract_source_url(search_result: str) -> Optional[str]:
    """Extract source URL from search result"""
    # Look for URLs in search result
    url_patterns = [
        r'https?://(?:www\.)?([a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)*)',
        r'(?:source|from|url)[:\s]+\s*(https?://[^\s]+)',
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, search_result, re.IGNORECASE)
        if match:
            if 'http' in match.group(0):
                return match.group(0).split()[0]
            else:
                return f"https://{match.group(1)}"
    
    return None


# ════════════════════════════════════════════════════════════════════════════════
# ENHANCED SYSTEM PROMPT WITH GENDER & COUNTRY
# ════════════════════════════════════════════════════════════════════════════════

STRICT_VALIDATOR_SYSTEM_PROMPT = """
YOU ARE A STRICT PERFUME DATA AUDITOR

Your ONLY job is to verify user-entered inventory data against authoritative source data.
The SOURCE DATA is the ground truth. User input is fallible and must be validated.

PRINCIPLE: SOURCE DATA > USER INPUT ALWAYS

⚠️ CRITICAL: GENDER RULES FOR THIS SYSTEM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ ADD GENDER (M/W) for FRAGRANCES ONLY:
   - Eau de Parfum (EDP)
   - Eau de Toilette (EDT)
   - Eau de Cologne (EDC)
   - Parfum/Extrait
   - Cologne
   Example: "D&G LIGHT BLUE W EDT 100ML" ✓

❌ DO NOT ADD GENDER for:
   - UNISEX FRAGRANCES → DO NOT add any gender keyword. By default, fragrances are unisex. Mention gender ONLY if specific to M or W.
     Example: "MONTALE DAY DREAMS EDP 100ML" (NOT "UNISEX", NOT "UNISEX M/W")
   
   - MAKEUP/COSMETIC ITEMS → NO gender whatsoever
     Includes: Lipstick, Mascara, Eyeliner, Lip Balm, Eyeshadow, Foundation, Blush, Bronzer
     Format: [BRAND] [PRODUCT_NAME] [SIZE] (NO gender, NO type like EDP/EDT)
     Example: "D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G" (NOT with W)
   
   - BODY PRODUCTS (non-fragrance) → NO gender if not explicitly fragrance
     Example: "GUY LAROCHE DRAKKAR NOIR SHOWER GEL 50ML"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL ADDITIONS FOR THIS SYSTEM:
→ For FRAGRANCES: extract and include GENDER in corrected_name
→ For MAKEUP: PRESERVE COMPLETE product name with ALL shade numbers and color names
→ For UNISEX: DO NOT add any gender keyword to the corrected name. Mention gender ONLY if specific to M or W.
→ ALWAYS extract and include COUNTRY in source_extracted
→ ALWAYS use brand abbreviations (D&G, JPG, CH, V&R, MJ)

Example corrected names:
  FRAGRANCES (with gender):
    "D&G LIGHT BLUE W EDT 100ML" (D&G abbreviation, W is gender for women)
    "DIOR SAUVAGE M EDT 75ML" (M for men)
    "MONTALE DAY DREAMS EDP 100ML" (UNISEX by default, no gender keyword added)
  
  MAKEUP (NO gender, preserve all details):
    "D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G" (complete shade preserved, NO W)
    "D&G GEMSTONE LIPSTICK 210 AMETHYST ROSE 3.5G" (full product info, NO W)
    "D&G GEMSTONE LIP BALM 00 DIAMOND 3.5G" (shade number + name, NO W)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRICT VALIDATION PROCEDURE:

1. EXTRACT from source data:
   - Exact product name from source
   - Brand (official name, then apply abbreviations)
   - Type: Find explicit mention (EDP/EDT/EDC/PARFUM/COLOGNE/BL/SHAMPOO/SG/DEO/AS)
   - Gender: Look for "for Men", "for Women", "Unisex", "Homme", "Femme"
   - Size: Extract all volumes, convert oz to ml (1oz = 29.57ml)
   - Country: Deduce from country indicators (Made in FR, Italy, USA, etc.)
   - Components: If giftset, extract EACH component's details separately

2. EXTRACT from user input:
   - Parse the name as entered
   - Identify fields they provided
   - Note what they got wrong or incomplete

3. VALIDATE EACH FIELD:
   For brand, type, gender, size, country:
   a) Is user input present?
   b) Does it match source data?
   c) If no match: use source data, mark as correction
   d) If match: confirm, mark as verified

4. BUILD CORRECTION using source data:
   - Start with source data as base
   - Apply brand abbreviations (D&G instead of DOLCE & GABBANA)
   - Apply naming convention (ALL UPPERCASE)
   
   IF FRAGRANCE (EDP, EDT, EDC, PARFUM, Cologne):
     Format: [BRAND] [FRAGRANCE] [GENDER] [TYPE] [SIZE]ML [CATEGORY_SUFFIX]
     - Include gender ONLY if specific to M or W.
     - UNISEX: DO NOT include any gender keyword.
     - Add category suffix if VIAL, MINI, MINI SET, or TESTER
     Example: "D&G LIGHT BLUE W EDT 100ML TESTER"
   
   IF MAKEUP/COSMETIC (Lipstick, Mascara, Eyeliner, etc.):
     Format: [BRAND] [PRODUCT_TYPE] [SHADE_NUMBER] [SHADE_NAME] [SIZE]
     - DO NOT include gender (no M, W, or UNISEX)
     - PRESERVE all shade numbers and color names completely
     - Keep original size format (3.5G, 8ML, etc.)
     - Do NOT add fragrance type
     - Add TESTER suffix if applicable
     Example: "D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G TESTER"
   
   - Mark all corrections with source attribution

5. DETERMINE CONFIDENCE:
   - High: Source data is clear, user input mostly correct
   - Medium: Some user errors, but source is clear
   - Low: Source is ambiguous or multiple errors

6. FLAG FOR REVIEW if:
   - STRICTLY flag for review (`needs_review`: true) if there is ANY discrepancy between user input and source data in: CATEGORY, SIZE, TYPE, or COUNTRY OF ORIGIN.
     (Example: Product is a TESTER unit, not a REGULAR sale unit. Gender and category updated to reflect authoritative source -> mark `needs_review: true`)
   - User was significantly wrong
   - Source data is ambiguous
   - Cannot verify a critical field
   - Product appears different from user's intent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL RULES (MUST FOLLOW):

Fragrance Name Validation:
  ✓ NEVER strip partial names, sub-lines, variants, or flankers (e.g. ELIXIR, INTENSE, ABSOLU, SPORT) if they are present in the user input or source data.
  ✓ Correct spelling mistakes based on the source data, but PRESERVE all relevant descriptors in the actual fragrance name.

Type Validation:
  ✓ "Eau de Parfum" = EDP
  ✓ "Eau de Toilette" = EDT
  ✓ If user said EDT but source says EDP, CORRECT IT

Gender Validation:
  ✓ FRAGRANCE ONLY: "for Men" = M, "Men's" = M, "Homme" = M → ADD to corrected_name
  ✓ FRAGRANCE ONLY: "for Women" = W, "Women's" = W, "Femme" = W → ADD to corrected_name
  ✓ UNISEX FRAGRANCE: DO NOT add any gender keyword.
  ✓ MAKEUP/COSMETICS: DO NOT ADD gender (no M, no W, no UNISEX)
  
  MAKEUP DETECTION - if product contains any of these, NO gender:
    Lipstick, Mascara, Eyeliner, Eyeshadow, Foundation, Blush, Bronzer, 
    Primer, Concealer, Lip Balm, Lip Gloss, Highlighter, etc.
  
  GENDER EXAMPLES:
    ✓ "DIOR SAUVAGE M EDT 100ML" (fragrance, men)
    ✓ "D&G LIGHT BLUE W EDT 100ML" (fragrance, women)
    ✓ "MONTALE DAY DREAMS EDP 100ML" (fragrance, unisex - no gender keyword added)
    ✗ "D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G" (makeup - NO gender added)
    ✗ "D&G MASCARA TOTAL BLACK W COSMETIC 8ML" (makeup - NO W added)

Country Validation:
  ✓ Look for "Made in FR", country names, etc.
  ✓ Use ISO 2-letter codes (FR, IT, US, DE, ES, etc.)
  ✓ Extract and include in output

Brand Abbreviations:
  ✓ DOLCE & GABBANA → D&G
  ✓ JEAN PAUL GAULTIER → JPG
  ✓ CAROLINA HERRERA → CH
  ✓ VIKTOR & ROLF → V&R
  ✓ MARC JACOBS → MJ

Size Format:
  ✓ Must be in ML for fragrances (e.g., 100ML not 100)
  ✓ Keep original format for makeup (3.5G, 8ML, etc.)
  ✓ Convert oz to ml: multiply by 29.57

Product Name Preservation (CRITICAL for makeup):
  ✓ PRESERVE complete lipstick names with shade numbers and colors
  ✓ Example: "D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G" (keep 415, SAPPHIRE, RUST)
  ✓ Example: "D&G GEMSTONE LIP BALM 00 DIAMOND 3.5G" (keep 00, DIAMOND)
  ✓ NEVER abbreviate or truncate makeup product names
  ✓ Include all shade numbers, color names, and descriptors

Giftset Components:
  ✓ VALIDATE EACH COMPONENT INDEPENDENTLY
  ✓ Add gender ONLY if it's a fragrance component
  ✓ NO gender for makeup components even in giftsets
  ✓ Expand abbreviations (H&B → AZZARO WANTED SHAMPOO)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT JSON SCHEMA:

{
  "corrected_name": "Corrected name - FORMAT DEPENDS ON PRODUCT TYPE:
    FRAGRANCE: [BRAND] [FRAGRANCE] [GENDER] [TYPE] [SIZE]ML [CATEGORY_SUFFIX]
      Example: D&G LIGHT BLUE W EDT 100ML TESTER
    MAKEUP: [BRAND] [PRODUCT] [SHADE_NUMBER] [SHADE_NAME] [SIZE] (NO gender, NO type)
      Example: D&G GEMSTONE LIPSTICK 415 SAPPHIRE RUST 3.5G
      UNISEX: [BRAND] [FRAGRANCE] [TYPE] [SIZE]ML (no gender keyword added)
        Example: MONTALE DAY DREAMS EDP 100ML",
  
  "source_extracted": {
    "brand": "Brand with abbreviations applied",
    "fragrance": "Fragrance name",
    "type": "EDP|EDT|etc",
    "category": "VIAL|MINI|MINI SET|TESTER|GIFTSET|REGULAR",
    "gender": "M|W|PH|UNISEX|None",
    "size_ml": "100ML",
    "country_of_origin": "ISO 2-letter code (FR, IT, US, etc.)",
    "full_description": "Complete source description"
  },
  
  "user_extracted": {
    "brand": "What user entered",
    "fragrance": "What user entered",
    "type": "What user entered",
    "category": "What user entered (may be empty)",
    "gender": "What user entered (may be empty)",
    "size_ml": "What user entered"
  },
  
  "validation": {
    "brand_match": true|false,
    "type_match": true|false,
    "category_match": true|false,
    "gender_match": true|false,
    "size_match": true|false,
    "country_match": true|false
  },
  
  "discrepancies": ["Array of all differences"],
  "corrections_applied": ["Array of corrections with reasons"],
  
  "source_used": "Domain",
  "source_url": "Full URL of source",
  "confidence": "High|Medium|Low",
  "needs_review": true|false,
  "review_reason": "If needs_review=true, explain why",
  "remarks": "Summary of all corrections"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXAMPLES:

Example 1: Gender and Abbreviation
  User: "DOLCE GABBANA LIGHT BLUE 100ML"
  Source: "Dolce & Gabbana Light Blue for Women 100ml"
  Output: "D&G LIGHT BLUE W EDP 100ML" ← Note: D&G abbreviation, W for women, EDP from source
  Remarks: "Brand abbreviated: DOLCE GABBANA → D&G | Gender added: W (for Women) | Type: EDP from source"

Example 2: Country Included
  User: "DIOR SAUVAGE EDT 75ML"
  Source: "Dior Sauvage Eau de Toilette for Men 75ml - Made in France"
  Output: "DIOR SAUVAGE M EDT 75ML"
  Country: "FR"
  Remarks: "Gender added: M (for Men) | Country deduced: FR (France)"

Example 3: Giftset with Gender
  User: "AZZARO WANTED EDT 100ML + EDT 10ML"
  Source: "Azzaro Wanted Eau de Parfum for Men 100ml + 10ml"
  Output: "AZZARO WANTED M EDP 100ML + EDP 10ML"
  Remarks: "Gender added: M | Component types corrected: EDT→EDP"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REMEMBER:
→ User input is NOT trusted
→ Source data IS authoritative
→ Include GENDER in corrected_name
→ Apply BRAND ABBREVIATIONS
→ Extract COUNTRY of origin
→ Explain every change
→ Flag when unsure
"""

# ════════════════════════════════════════════════════════════════════════════════
# VALIDATION FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

def validate_with_strict_gemini(item: dict, search_result: str, max_retries: int = 5) -> dict:
    """
    STRICT validation using Gemini with gender, country, and brand abbreviations.
    Treats source data as ground truth.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Extract data from source for context
    source_brand = extract_brand(search_result)
    source_type = extract_type(search_result)
    source_gender = extract_gender(search_result)
    source_size = extract_size_ml(search_result)
    source_country = extract_country(search_result)
    source_url = extract_source_url(search_result)
    
    # Extract user data
    user_name = item.get("Name", "").strip()
    
    # Build detailed prompt
    prompt = f"""
TASK: Strictly validate perfume inventory entry against source data.
PRINCIPLE: Source data is authoritative. User input is fallible.

USER ENTERED:
{json.dumps(item, indent=2)}

SEARCH RESULT (AUTHORITATIVE SOURCE):
{search_result}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXTRACTED DATA FOR REFERENCE:

From Source:
- Brand: {source_brand or 'Not found'}
- Type: {source_type or 'Not found'}
- Gender: {source_gender or 'Not found'}
- Size: {source_size or 'Not found'}
- Country: {source_country or 'Not found'}
- URL: {source_url or 'Not found'}

From User Input (to validate):
- Full entry: {user_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR TASK:

1. Extract ALL details from source (brand with abbreviations, type, gender, size, country)
2. Compare user input to source data field-by-field
3. Use SOURCE data as the ground truth
4. Build corrected name (include GENDER ONLY if M or W): [BRAND] [FRAGRANCE] [GENDER] [TYPE] [SIZE]ML
5. Apply brand abbreviations (D&G, JPG, CH, etc.)
6. Include country_of_origin in output
7. Document all discrepancies
8. Explain why each correction was made

Return ONLY valid JSON (no markdown):

{{
  "corrected_name": "BRAND FRAGRANCE GENDER TYPE SIZEML [CATEGORY_SUFFIX] - includes gender only if M or W, brand abbreviated",
  "source_extracted": {{
    "brand": "Brand (with abbreviations)",
    "fragrance": "Fragrance",
    "type": "EDP|EDT|etc",
    "category": "VIAL|MINI|MINI SET|TESTER|GIFTSET|REGULAR",
    "gender": "M|W|UNISEX|None",
    "size_ml": "100ML",
    "country_of_origin": "FR|IT|US|etc",
    "full_description": "Source description"
  }},
  "user_extracted": {{
    "brand": "What user entered",
    "fragrance": "What user entered",
    "type": "What user entered",
    "category": "What user entered or empty",
    "gender": "What user entered or empty",
    "size_ml": "What user entered"
  }},
  "validation": {{
    "brand_match": true|false,
    "type_match": true|false,
    "category_match": true|false,
    "gender_match": true|false,
    "size_match": true|false,
    "country_match": true|false
  }},
  "discrepancies": ["List of all differences"],
  "corrections_applied": ["List of corrections with reasons"],
  "source_used": "domain.com",
  "source_url": "{source_url or ''}",
  "confidence": "High|Medium|Low",
  "needs_review": false,
  "review_reason": null,
  "remarks": "Summary of all corrections made"
}}
"""
    
    base_delay = 6.0
    for attempt in range(1, max_retries + 1):
        try:
            model = genai.GenerativeModel(
                model_name="gemini-3.1-flash-lite",
                system_instruction=STRICT_VALIDATOR_SYSTEM_PROMPT,
            )
            
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            validation = json.loads(raw)
            
            # Ensure source_url is included
            if source_url and not validation.get('source_url'):
                validation['source_url'] = source_url
            
            # Log validation details
            log.info(f"  ✓ Source: {validation.get('source_extracted', {}).get('brand', 'N/A')} "
                    f"| Type: {validation.get('source_extracted', {}).get('type', 'N/A')} "
                    f"| Gender: {validation.get('source_extracted', {}).get('gender', 'N/A')} "
                    f"| Country: {validation.get('source_extracted', {}).get('country_of_origin', 'N/A')}")
            
            return validation
            
        except json.JSONDecodeError as e:
            log.error(f"  ❌ JSON parse error: {e}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            return {
                "corrected_name": user_name,
                "remarks": "Validation error - manual review needed",
                "confidence": "Low",
                "needs_review": True,
                "source_url": source_url
            }
        
        except Exception as e:
            err_msg = str(e)
            if any(k in err_msg for k in ["429", "Quota", "ResourceExhausted"]):
                wait = base_delay * (2 ** (attempt - 1))
                log.warning(f"  ⚠ Rate limited. Sleeping {wait:.2f}s...")
                time.sleep(wait)
            else:
                log.error(f"  ❌ Validation error: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return {
                    "corrected_name": user_name,
                    "remarks": "Validation error - manual review needed",
                    "confidence": "Low",
                    "needs_review": True,
                    "source_url": source_url
                }
    
    return {
        "corrected_name": user_name,
        "remarks": "Max retries exceeded",
        "confidence": "Low",
        "needs_review": True,
        "source_url": source_url
    }


# ════════════════════════════════════════════════════════════════════════════════
# CSV OUTPUT WITH GENDER, COUNTRY, AND HYPERLINKS
# ════════════════════════════════════════════════════════════════════════════════

def normalize_source_name(source: str) -> str:
    """Normalize source domain name for display"""
    if not source:
        return "Unknown"
    
    # Extract domain from URL
    match = re.search(r'https?://(?:www\.)?([^/]+)', source)
    if match:
        return match.group(1)
    
    return source

def results_to_csv(results: list[dict]) -> str:
    """
    Convert validation results to CSV with gender, country, and hyperlinked source.
    """
    if not results:
        return ""
    
    original_fields = [f for f in list(results[0].get("original_data", {}).keys()) if f and f.strip()]
    extra_fields = [
        "Corrected Name", 
        "Source Name",
        "Category",
        "Gender", 
        "Type", 
        "Size (ML)", 
        "Country of Origin",
        "Remarks", 
        "Source Used", 
        "Confidence", 
        "Needs Review"
    ]
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=original_fields + extra_fields)
    writer.writeheader()

    for r in results:
        row = {k: r.get("original_data", {}).get(k, "") for k in original_fields}
        
        source_url = r.get("source_url", "")
        source_extracted = r.get("source_extracted", {})
        
        # Build hyperlink
        label = normalize_source_name(source_extracted.get("brand", r.get("source_used", "Unknown")))
        source_link = f'=HYPERLINK("{source_url}", "{label}")' if source_url else label
        
        row.update({
            "Corrected Name": r.get("corrected_name", ""),
            "Source Name": source_extracted.get("full_description", source_extracted.get("fragrance", "")),
            "Category": source_extracted.get("category", r.get("category", "")),
            "Gender": source_extracted.get("gender", r.get("gender", "")),
            "Type": source_extracted.get("type", ""),
            "Size (ML)": source_extracted.get("size_ml", ""),
            "Country of Origin": source_extracted.get("country_of_origin", ""),
            "Remarks": r.get("remarks", ""),
            "Source Used": source_link,
            "Confidence": r.get("confidence", ""),
            "Needs Review": "YES" if r.get("needs_review") else "NO",
        })
        writer.writerow(row)
    
    return output.getvalue()

def compute_stats(results: list[dict]) -> dict:
    """Compute validation statistics"""
    review = [r for r in results if r.get("needs_review") or "mismatch" in str(r.get("remarks")).lower()]
    return {
        "total": len(results),
        "ok": len([r for r in results if r.get("remarks") == "OK"]),
        "corrected": len([r for r in results if not r.get("needs_review") and r.get("remarks") != "OK"]),
        "review": len(review),
        "review_items": [r.get("original_entry", "") for r in review],
    }

# ════════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (stub - implement based on your existing code)
# ════════════════════════════════════════════════════════════════════════════════

def parse_csv(csv_text: str) -> list[dict]:
    """Parse CSV text into list of dicts"""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    return [row for row in reader]

TRUSTED_SITES = [
    ("ebay.com",             10),  
    ("jomashop.com",          9),  
    ("fragrancenet.com",      8),  
    ("sephora.com",           8),  
    ("nordstrom.com",         8),  
    ("fragrantica.com",       8),  
    ("basenotes.net",         7),  
    ("parfumo.com",           7),  
]
TRUSTED_DOMAINS = {site: score for site, score in TRUSTED_SITES}

def get_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def trust_score(url: str) -> int:
    domain = get_domain(url)
    for trusted_domain, score in TRUSTED_DOMAINS.items():
        if trusted_domain in domain: return score
    return 0

def _search_serper(query: str, num: int) -> list[dict]:
    if not SERPER_API_KEY and not SERPER_API_KEY_BKP:
        raise ValueError("SERPER_API_KEY and SERPER_API_KEY_BKP are missing")
    
    keys_to_try = [k for k in [SERPER_API_KEY, SERPER_API_KEY_BKP] if k]
    res = None
    
    for i, key in enumerate(keys_to_try):
        try:
            res = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": query, "num": num},
                timeout=10,
            )
            res.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if i < len(keys_to_try) - 1:
                log.warning(f"Serper API key failed ({e}), trying backup...")
            else:
                raise

    data = res.json()
    results = []
    kg = data.get("knowledgeGraph", {})
    if kg.get("title"):
        kg_text = f"Title: {kg['title']}"
        if kg.get("type"): kg_text += f" | Type: {kg['type']}"
        if kg.get("description"): kg_text += f" | {kg['description']}"
        results.append({
            "title": kg.get("title", ""),
            "url": kg.get("website", ""),
            "snippet": kg_text,
            "trust_score": 10,
            "source_label": "Google Knowledge Graph",
        })
    for r in data.get("organic", []):
        url = r.get("link", "")
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("snippet", ""),
            "trust_score": trust_score(url),
            "source_label": get_domain(url) or "unknown",
        })
    return results

def _search_brave(query: str, num: int) -> list[dict]:
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY is missing")
    res = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
        params={"q": query, "count": min(num, 20)},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    results = []
    for r in data.get("web", {}).get("results", []):
        url = r.get("url", "")
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("description", ""),
            "trust_score": trust_score(url),
            "source_label": get_domain(url) or "unknown",
        })
    return results

def _search_google_custom(query: str, num: int) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        raise ValueError("GOOGLE_SEARCH credentials missing")
    res = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"q": query, "key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_SEARCH_CX, "num": min(num, 10)},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    results = []
    for r in data.get("items", []):
        url = r.get("link", "")
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("snippet", ""),
            "trust_score": trust_score(url),
            "source_label": get_domain(url) or "unknown",
        })
    return results

def execute_search_query(query: str, num: int = 5) -> list[dict]:
    try:
        return _search_serper(query, num)
    except Exception as e:
        log.warning(f"  [Fallback 1] Serper failed ({e}). Trying Brave Search...")
    try:
        return _search_brave(query, num)
    except Exception as e:
        log.warning(f"  [Fallback 2] Brave failed ({e}). Trying Google Custom...")
    try:
        return _search_google_custom(query, num)
    except Exception as e:
        log.error(f"  ❌ All search providers exhausted. Query: {query}")
    return []

def format_results_for_llm(results: list[dict], item_name: str) -> str:
    if not results: return "No results found from any source."
    sorted_results = sorted(results, key=lambda x: x["trust_score"], reverse=True)
    lines = [f"SEARCH RESULTS FOR: {item_name}", ""]
    for i, r in enumerate(sorted_results[:6], 1):  
        lines.append(f"[{i}] {r['title']}\n    Source : {r['source_label']} [Trust: {r['trust_score']}]\n    URL    : {r['url']}\n    Info   : {r['snippet']}\n")
    return "\n".join(lines)

def deduplicate_results(results: list[dict]) -> list[dict]:
    seen_domains = {}
    for r in sorted(results, key=lambda x: x["trust_score"], reverse=True):
        domain = get_domain(r["url"]) or r["source_label"]
        if domain not in seen_domains: seen_domains[domain] = r
    return list(seen_domains.values())

def search_product(item_name: str) -> str:
    """Search for product using Serper API"""
    all_results = []

    ebay_results = [r for r in execute_search_query(f"site:ebay.com {item_name} perfume") if r["trust_score"] == 10]
    if ebay_results:
        log.info(f"  ✓ Found {len(ebay_results)} authoritative records on eBay")
        all_results.extend(ebay_results)

    joma_results = [r for r in execute_search_query(f"site:jomashop.com {item_name} perfume") if r["trust_score"] == 9]
    if joma_results:
        log.info(f"  ✓ Found {len(joma_results)} fallback records on Jomashop")
        all_results.extend(joma_results)

    if not all_results:
        broad_results = execute_search_query(f"{item_name} perfume fragrance EDP EDT ml", num=5)
        all_results.extend(broad_results)

    return format_results_for_llm(deduplicate_results(all_results), item_name)

def excel_to_csv(excel_bytes: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    output = io.StringIO()
    writer = csv.writer(output)
    for row in ws.iter_rows(values_only=True):
        writer.writerow([str(v) if v is not None else "" for v in row])
    return output.getvalue()

def fetch_inventory_email() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch inventory from Gmail"""
    import imaplib
    import email
    from email.header import decode_header

    log.info("Connecting to Gmail via IMAP...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        search_criteria = ['(SUBJECT "inventory")', '(SUBJECT "new items")', '(SUBJECT "fragrance")', '(SUBJECT "perfume")', '(SUBJECT "stock")']
        all_ids = []
        for criteria in search_criteria:
            _, data = mail.search(None, criteria)
            if data[0]:
                all_ids.extend(data[0].split())

        if not all_ids:
            log.warning("No inventory email found in inbox.")
            mail.logout()
            return None, None, None

        latest_id = sorted(set(all_ids))[-1]
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject_raw = msg["Subject"] or "Inventory"
        subject = decode_header(subject_raw)[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()

        sender = msg.get("From", "")
        log.info(f"Found email: '{subject}' from {sender}")

        csv_content = None
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename() or ""

            if any(ext in filename.lower() for ext in [".csv", ".xlsx", ".xls"]):
                payload = part.get_payload(decode=True)
                if filename.lower().endswith(".csv"):
                    csv_content = payload.decode("utf-8", errors="replace")
                elif filename.lower().endswith((".xlsx", ".xls")):
                    csv_content = excel_to_csv(payload)
                break
            elif content_type == "text/plain" and not csv_content:
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                if "," in body and "\n" in body and len(body.strip().split("\n")) > 2:
                    csv_content = body

        mail.logout()
        return csv_content, subject, sender
    except Exception as e:
        log.error(f"Gmail IMAP error: {e}")
        raise

def get_item_name(item: dict) -> str:
    """Get item name from dictionary"""
    for key, val in item.items():
        if key and isinstance(key, str):
            if any(k in key.lower() for k in ["description", "name", "item", "fragrance"]):
                if val and isinstance(val, str) and val.strip():
                    return val.strip()
    for val in item.values():
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return "Unknown Item"

def get_item_search_key(item: dict) -> Optional[str]:
    """Get search key from item"""
    for key in item:
        if any(k in key.lower() for k in ["gtin", "ean", "upc", "barcode"]):
            val = item[key]
            if isinstance(val, str) and val.strip(): 
                return val.strip()
    return get_item_name(item)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════════

def main():
    """Main orchestrator - runs the validation pipeline"""
    log.info("=" * 80)
    log.info("STRICT PERFUME VALIDATOR - Starting pipeline")
    log.info("=" * 80)
    log.info("Key Features:")
    log.info("  ✓ Brand abbreviations (D&G, JPG, CH, etc.)")
    log.info("  ✓ Gender extraction and inclusion")
    log.info("  ✓ Country of origin extraction")
    log.info("  ✓ Source hyperlinks in CSV")
    log.info("  ✓ Complete audit trail")
    log.info("=" * 80)
    
    # Step 1: Get inventory (email or file)
    log.info("\n[Step 1] Fetching inventory...")
    csv_text, subject, sender = fetch_inventory_email()
    if not csv_text:
        log.warning("  No email found, checking for local CSV file...")
        try:
            with open("data/items.csv", "r", encoding="utf-8") as f:
                csv_text = f.read()
            sender = NOTIFY_EMAIL
            subject = "Local validation"
        except FileNotFoundError:
            csv_text = None
    
    if not csv_text:
        log.error("  ❌ No inventory data found")
        return
    
    # Step 2: Parse CSV
    log.info("\n[Step 2] Parsing CSV...")
    items = parse_csv(csv_text)
    log.info(f"  ✓ Parsed {len(items)} items")
    
    # Step 3-4: Validate each item
    log.info("\n[Step 3-4] Validating items (STRICT mode)...")

    # For testing, run check for the first 30 items only
    items = items[:30]
    results = []
    
    for i, item in enumerate(items, 1):
        item_name = get_item_name(item)
        log.info(f"\n  [{i}/{len(items)}] Validating: {item_name}")
        
        # Build search query combining name and GTIN for better accuracy
        search_key = get_item_search_key(item)
        search_query = f"{item_name} {search_key}" if search_key and search_key != item_name else item_name
        
        # Search for product
        search_result = search_product(search_query)
        if not search_result or search_result == "No results found from any source.":
            log.warning(f"    ⚠ No search results found")
            results.append({
                "original_entry": item_name,
                "original_data": item,
                "corrected_name": item_name,
                "remarks": "Not found - manual review",
                "confidence": "Low",
                "needs_review": True
            })
            continue
        
        # Validate with STRICT logic
        validation = validate_with_strict_gemini(item, search_result)
        
        # Add original entry for audit trail
        validation["original_entry"] = item_name
        validation["original_data"] = item
        results.append(validation)
        
        time.sleep(1)  # Rate limiting
    
    # Step 5: Output results
    log.info(f"\n[Step 5] Generating output...")
    
    # Compute stats
    stats = compute_stats(results)
    
    log.info(f"  Total validated: {stats['total']}")
    log.info(f"  Needs review: {stats['review']}")
    
    # Write output CSV
    output_file = results_to_csv(results)
    
    os.makedirs("output", exist_ok=True)
    destination_path = "output/test_output.csv"
    with open(destination_path, "w", encoding="utf-8") as f:
        f.write(output_file)
    
    log.info(f"  ✓ Results saved: {destination_path}")
    log.info("\n" + "=" * 80)
    log.info("✓ VALIDATION COMPLETE")
    log.info("=" * 80)


if __name__ == "__main__":
    main()