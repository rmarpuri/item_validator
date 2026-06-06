# STRICT VALIDATOR — Detailed Validation Walkthroughs

## Example 1: Simple Product - No Issues

### Input
```
User entered: "DIOR SAUVAGE EDT 75ML"
```

### Search Result
```
[1] Dior Sauvage Eau de Toilette 75ml
    For Men
    Source: jomashop.com
    Price: $75.00
```

### Extraction Process

**From Source:**
```
brand: "DIOR"
fragrance: "SAUVAGE"
type: "EDT" (because "Eau de Toilette")
gender: "M" (because "For Men")
size_ml: "75ML"
country_of_origin: "FR" (Dior is French)
```

**From User Input:**
```
brand: "DIOR"
fragrance: "SAUVAGE"
type: "EDT"
gender: (empty)
size_ml: "75ML"
```

### Validation Results

| Field | User | Source | Match? | Remark |
|-------|------|--------|--------|--------|
| Brand | DIOR | DIOR | ✅ | Verified |
| Fragrance | SAUVAGE | SAUVAGE | ✅ | Verified |
| Type | EDT | EDT | ✅ | Verified |
| Gender | (empty) | M | ❌ | Missing |
| Size | 75ML | 75ML | ✅ | Verified |

### Discrepancies Found
```json
[
  "Gender missing: user didn't specify, source indicates for Men"
]
```

### Corrections Applied
```json
[
  "Gender added: M (source indicates For Men)"
]
```

### Output JSON
```json
{
  "corrected_name": "DIOR SAUVAGE M EDT 75ML",
  
  "source_extracted": {
    "brand": "DIOR",
    "fragrance": "SAUVAGE",
    "type": "EDT",
    "gender": "M",
    "size_ml": "75ML",
    "country_of_origin": "FR",
    "full_description": "Dior Sauvage Eau de Toilette for Men 75ml"
  },
  
  "user_extracted": {
    "brand": "DIOR",
    "fragrance": "SAUVAGE",
    "type": "EDT",
    "gender": "",
    "size_ml": "75ML"
  },
  
  "validation": {
    "brand_match": true,
    "type_match": true,
    "gender_match": false,
    "size_match": true,
    "country_match": false
  },
  
  "discrepancies": [
    "Gender missing: user didn't specify, source says for Men"
  ],
  
  "corrections_applied": [
    "Gender added: M (source indicates For Men)"
  ],
  
  "source_used": "jomashop.com",
  "confidence": "High",
  "needs_review": false,
  "review_reason": null,
  "remarks": "Gender added: M (source indicates For Men)"
}
```

### Why This Output is Correct
- ✅ Source data extracted completely
- ✅ User input analyzed accurately
- ✅ Discrepancy identified (missing gender)
- ✅ Correction made from source
- ✅ Confidence is High (source is clear, trusted domain)
- ✅ needs_review is false (source-verified addition)
- ✅ Audit trail complete

---

## Example 2: Type Mismatch - Critical Error

### Input
```
User entered: "AZZARO WANTED EDT 100ML"
```

### Search Result
```
[1] Azzaro Wanted Fragrance Gift Set
    Main fragrance: Wanted Eau de Parfum 100ml
    For Men
    Source: sephora.com
```

### Extraction Process

**From Source:**
```
brand: "AZZARO"
fragrance: "WANTED"
type: "EDP" (because "Eau de Parfum" explicitly stated)
gender: "M" (because "For Men")
size_ml: "100ML"
country_of_origin: "FR" (Azzaro is French)
```

**From User Input:**
```
brand: "AZZARO"
fragrance: "WANTED"
type: "EDT" ← USER ENTERED WRONG TYPE
gender: (empty)
size_ml: "100ML"
```

### Validation Results

| Field | User | Source | Match? | Remark |
|-------|------|--------|--------|--------|
| Brand | AZZARO | AZZARO | ✅ | Verified |
| Fragrance | WANTED | WANTED | ✅ | Verified |
| Type | EDT | EDP | ❌ | **MISMATCH** |
| Gender | (empty) | M | ❌ | Missing |
| Size | 100ML | 100ML | ✅ | Verified |

### Discrepancies Found
```json
[
  "Type mismatch: user said EDT, source clearly states Eau de Parfum (EDP)",
  "Gender missing: user didn't specify, source indicates For Men"
]
```

### Corrections Applied
```json
[
  "Type corrected: EDT → EDP (source shows Eau de Parfum)",
  "Gender added: M (source indicates For Men)"
]
```

### Output JSON
```json
{
  "corrected_name": "AZZARO WANTED M EDP 100ML",
  
  "source_extracted": {
    "brand": "AZZARO",
    "fragrance": "WANTED",
    "type": "EDP",
    "gender": "M",
    "size_ml": "100ML",
    "country_of_origin": "FR",
    "full_description": "Azzaro Wanted Eau de Parfum for Men 100ml"
  },
  
  "user_extracted": {
    "brand": "AZZARO",
    "fragrance": "WANTED",
    "type": "EDT",
    "gender": "",
    "size_ml": "100ML"
  },
  
  "validation": {
    "brand_match": true,
    "type_match": false,
    "gender_match": false,
    "size_match": true,
    "country_match": false
  },
  
  "discrepancies": [
    "Type mismatch: user said EDT, source clearly states Eau de Parfum (EDP)",
    "Gender missing: user didn't specify, source indicates For Men"
  ],
  
  "corrections_applied": [
    "Type corrected: EDT → EDP (source explicitly shows Eau de Parfum from Sephora)",
    "Gender added: M (source indicates For Men)"
  ],
  
  "source_used": "sephora.com",
  "confidence": "High",
  "needs_review": false,
  "review_reason": null,
  "remarks": "Type corrected: EDT → EDP (source says Eau de Parfum) | Gender added: M (for Men)"
}
```

### Why This Output is Correct
- ✅ **Type mismatch detected** — User was factually wrong
- ✅ **Correction made from source** — EDP is what source says
- ✅ **Confidence is High** — Sephora is trusted, source is explicit
- ✅ **needs_review is false** — Source-verified correction, user error is clear
- ✅ **Audit trail shows error** — Discrepancies array documents user error
- ✅ **Detailed remarks explain why** — "source says Eau de Parfum"

### Key Learning
This shows the DIFFERENCE between old and new system:
- **OLD SYSTEM:** Would accept EDT as user entered, maybe just note it
- **NEW SYSTEM:** CORRECTS to EDP because source is authoritative

---

## Example 3: Giftset with Multiple Component Errors

### Input
```
User entered: "AZZARO WANTED EDT 100ML + EDT 10ML + H&B 75ML"
```

### Search Result
```
[1] Azzaro Wanted Fragrance Gift Set
    Includes:
    - Wanted Eau de Parfum 3.4 oz (100ml)
    - Wanted Eau de Parfum 0.3 oz (10ml)  
    - Hair & Body Shampoo 2.5 oz (75ml)
    Source: jomashop.com
```

### Component-by-Component Extraction

**Component 1: Main fragrance**

From Source:
```
brand: "AZZARO"
fragrance: "WANTED"
type: "EDP" (Eau de Parfum)
size_ml: "100ML"
```

From User:
```
type: "EDT" ← WRONG
```

**Component 2: Travel size**

From Source:
```
brand: "AZZARO"
fragrance: "WANTED"
type: "EDP" (Eau de Parfum)
size_ml: "10ML"
```

From User:
```
type: "EDT" ← WRONG
```

**Component 3: Non-fragrance**

From Source:
```
brand: "AZZARO"
product: "WANTED HAIR & BODY SHAMPOO"
type: "SHAMPOO"
size_ml: "75ML"
category: "Non-Fragrance"
```

From User:
```
product: "H&B" ← ABBREVIATED
```

### Validation Results

**Component 1:**
```
Type: EDT (user) vs EDP (source) → MISMATCH
Correction: Change to EDP
```

**Component 2:**
```
Type: EDT (user) vs EDP (source) → MISMATCH
Correction: Change to EDP
```

**Component 3:**
```
Name: H&B (user) vs AZZARO WANTED SHAMPOO (source) → INCOMPLETE
Correction: Expand to full name with brand
Category: SHAMPOO detected (non-fragrance)
```

### Discrepancies Found
```json
[
  "Component 1 type mismatch: user said EDT, source says Eau de Parfum (EDP)",
  "Component 2 type mismatch: user said EDT, source says Eau de Parfum (EDP)",
  "Component 3 product name abbreviated: user wrote H&B, should be full name AZZARO WANTED SHAMPOO",
  "Component 3 is non-fragrance item: not a fragrance, is a shampoo"
]
```

### Corrections Applied
```json
[
  "Component 1 type corrected: EDT → EDP (source shows Eau de Parfum)",
  "Component 2 type corrected: EDT → EDP (source shows Eau de Parfum)",
  "Component 3 product expanded: H&B → AZZARO WANTED SHAMPOO (full source name)",
  "Component 3 marked as non-fragrance: Shampoo type from source"
]
```

### Output JSON
```json
{
  "corrected_name": "AZZARO WANTED EDP 100ML + EDP 10ML + AZZARO WANTED SHAMPOO 75ML",
  
  "source_extracted": {
    "brand": "AZZARO",
    "fragrance": "WANTED",
    "type": "EDP",
    "gender": null,
    "size_ml": "100ML + 10ML + 75ML",
    "country_of_origin": "FR",
    "full_description": "Azzaro Wanted Eau de Parfum 100ml + 10ml + Hair & Body Shampoo 75ml"
  },
  
  "user_extracted": {
    "brand": "AZZARO",
    "fragrance": "WANTED",
    "type": "EDT",
    "gender": null,
    "size_ml": "100ML + 10ML + 75ML"
  },
  
  "validation": {
    "brand_match": true,
    "type_match": false,
    "gender_match": true,
    "size_match": true,
    "country_match": false
  },
  
  "discrepancies": [
    "Component 1 type mismatch: user said EDT, source says Eau de Parfum (EDP)",
    "Component 2 type mismatch: user said EDT, source says Eau de Parfum (EDP)",
    "Component 3 name abbreviated: user wrote H&B, source shows full name",
    "Component 3 is non-fragrance: Shampoo, not a fragrance"
  ],
  
  "corrections_applied": [
    "Component 1 type corrected: EDT → EDP (source explicitly shows Eau de Parfum)",
    "Component 2 type corrected: EDT → EDP (source explicitly shows Eau de Parfum)",
    "Component 3 expanded: H&B → AZZARO WANTED SHAMPOO (full product name from source)",
    "Component 3 marked as non-fragrance item: Shampoo type"
  ],
  
  "source_used": "jomashop.com",
  "confidence": "High",
  "needs_review": false,
  "review_reason": null,
  "remarks": "Component 1 type corrected: EDT→EDP | Component 2 type corrected: EDT→EDP | Component 3 expanded: H&B→AZZARO WANTED SHAMPOO | Non-fragrance item included"
}
```

### Why This Output is Correct
- ✅ **Each component validated independently** — No component overlooked
- ✅ **Type corrections made for components 1 & 2** — User was wrong twice, source is clear
- ✅ **Component 3 expanded** — H&B now shows full name: AZZARO WANTED SHAMPOO
- ✅ **Non-fragrance detected** — Shampoo is correctly identified
- ✅ **Confidence is High** — Jomashop is trusted, source is detailed
- ✅ **needs_review is false** — All corrections are source-verified, user errors are clear
- ✅ **Detailed remarks** — Each component correction explained

### Key Learning
This shows the power of component-level validation:
- **User got BOTH fragrance components wrong** (EDT vs EDP)
- **OLD SYSTEM:** Would accept as-is or make minor notes
- **NEW SYSTEM:** Corrects both based on source, identifies non-fragrance item, expands abbreviation

---

## Example 4: Source Ambiguous - Medium Confidence

### Input
```
User entered: "MYSTERY BRAND MYSTERY FRAGRANCE"
```

### Search Result
```
[1] Mystery Brand Mystery Fragrance
    Could be Eau de Parfum or Eau de Toilette
    Size: around 100ml
    For men or women unclear
    Source: smallretailer.com
```

### Extraction Process

**From Source (AMBIGUOUS):**
```
brand: "MYSTERY BRAND" ✓ Clear
fragrance: "MYSTERY FRAGRANCE" ✓ Clear
type: ??? (Could be EDP or EDT) ← AMBIGUOUS
gender: ??? (Could be M or W) ← AMBIGUOUS
size_ml: "100ML" (approximately)
country_of_origin: ??? ← CANNOT DETERMINE
```

**From User Input:**
```
brand: "MYSTERY BRAND" ✓
fragrance: "MYSTERY FRAGRANCE" ✓
type: (not specified) ← MISSING
gender: (not specified) ← MISSING
size_ml: (not specified) ← MISSING
```

### Validation Results

| Field | User | Source | Match? | Issue |
|-------|------|--------|--------|--------|
| Brand | MYSTERY BRAND | MYSTERY BRAND | ✅ | Verified |
| Fragrance | MYSTERY FRAGRANCE | MYSTERY FRAGRANCE | ✅ | Verified |
| Type | (empty) | ??? (EDP or EDT) | ❌ | **Cannot determine** |
| Gender | (empty) | ??? (M or W) | ❌ | **Cannot determine** |
| Size | (empty) | ~100ML | ❌ | **Approximate only** |

### Discrepancies Found
```json
[
  "Type cannot be determined: source doesn't clearly specify EDP vs EDT",
  "Gender cannot be determined: source doesn't indicate M or W",
  "Size is approximate: source shows around 100ml but not exact",
  "Country of origin cannot be determined from source"
]
```

### Why needs_review = true

Source data is too ambiguous to make confident corrections. User should be consulted.

### Output JSON
```json
{
  "corrected_name": "MYSTERY BRAND MYSTERY FRAGRANCE",
  
  "source_extracted": {
    "brand": "MYSTERY BRAND",
    "fragrance": "MYSTERY FRAGRANCE",
    "type": null,
    "gender": null,
    "size_ml": "~100ML",
    "country_of_origin": null,
    "full_description": "Mystery Brand Mystery Fragrance - type and gender unclear from source"
  },
  
  "user_extracted": {
    "brand": "MYSTERY BRAND",
    "fragrance": "MYSTERY FRAGRANCE",
    "type": null,
    "gender": null,
    "size_ml": null
  },
  
  "validation": {
    "brand_match": true,
    "type_match": null,
    "gender_match": null,
    "size_match": null,
    "country_match": null
  },
  
  "discrepancies": [
    "Type cannot be determined: source doesn't clearly specify EDP vs EDT",
    "Gender cannot be determined: source doesn't indicate M or W",
    "Size is approximate: source shows around 100ml but not exact",
    "Country of origin cannot be determined from source"
  ],
  
  "corrections_applied": [],
  
  "source_used": "smallretailer.com",
  "confidence": "Low",
  "needs_review": true,
  "review_reason": "Source data is ambiguous on critical fields (type, gender). Cannot definitively extract from provided search results. Manual verification recommended.",
  
  "remarks": "Source ambiguous - Manual review required to confirm type (EDP vs EDT), gender (M vs W), and exact size"
}
```

### Why This Output is Correct
- ✅ **Confidence is Low** — Source data is unclear
- ✅ **needs_review is true** — Cannot validate without ambiguity
- ✅ **review_reason explained** — States exactly why review is needed
- ✅ **No incorrect corrections made** — Doesn't guess
- ✅ **Discrepancies documented** — All ambiguities listed

### Key Learning
This shows responsible handling of uncertain data:
- **NEW SYSTEM doesn't guess** — When source is unclear, flags it
- **Audit trail shows why** — Every discrepancy documented
- **User gets clear direction** — Knows exactly what needs manual review

---

## Example 5: Wrong Product Detected - needs_review = true

### Input
```
User entered: "CHANEL NO5 EDT 100ML"
```

### Search Result
```
[1] Chanel Chance Eau de Parfum 100ml
    For Women
    This is a different product from No5
```

### Analysis

**User's Intent:**
- Product: Chanel No. 5 (classic fragrance, has EDP and EDT versions)

**Source Data:**
- Product: Chanel Chance (completely different fragrance)
- Type: EDP

### Validation Results

| Field | User | Source | Issue |
|-------|------|--------|--------|
| Brand | CHANEL | CHANEL | ✅ Same brand |
| Fragrance | NO5 | CHANCE | ❌ **DIFFERENT PRODUCT** |
| Type | EDT | EDP | Irrelevant (wrong product) |

### Discrepancies Found
```json
[
  "PRODUCT MISMATCH: User looking for Chanel No. 5, source returned Chanel Chance",
  "These are different fragrances from same brand"
]
```

### Why needs_review = true

This is a CRITICAL issue. Source data doesn't match what user is looking for. This might be:
- Search returned wrong result
- User typed wrong name
- Product doesn't exist in database

Cannot proceed without human verification.

### Output JSON
```json
{
  "corrected_name": "CHANEL NO5 EDT 100ML",
  
  "source_extracted": {
    "brand": "CHANEL",
    "fragrance": "CHANCE",
    "type": "EDP",
    "gender": "W",
    "size_ml": "100ML",
    "country_of_origin": "FR",
    "full_description": "Chanel Chance Eau de Parfum for Women 100ml"
  },
  
  "user_extracted": {
    "brand": "CHANEL",
    "fragrance": "NO5",
    "type": "EDT",
    "gender": null,
    "size_ml": "100ML"
  },
  
  "validation": {
    "brand_match": true,
    "type_match": false,
    "gender_match": false,
    "size_match": true,
    "country_match": false
  },
  
  "discrepancies": [
    "PRODUCT MISMATCH: User fragrance is No. 5, source fragrance is Chance - these are different products",
    "Type mismatch: User said EDT, source shows EDP",
    "Gender mismatch: User didn't specify, source shows Women"
  ],
  
  "corrections_applied": [],
  
  "source_used": "search results",
  "confidence": "Low",
  "needs_review": true,
  "review_reason": "CRITICAL: Product mismatch detected. User entered Chanel No. 5, but search returned Chanel Chance (different fragrance). Source data does not match user's requested product. Possible causes: (1) wrong search results returned, (2) user typed wrong product name, (3) product not found in database. MANUAL VERIFICATION REQUIRED.",
  
  "remarks": "Product mismatch: No. 5 vs Chance - different fragrances"
}
```

### Why This Output is Correct
- ✅ **Confidence is Low** — Different products detected
- ✅ **needs_review is true** — Cannot proceed without verification
- ✅ **review_reason is detailed** — Explains the problem clearly
- ✅ **No corrections made** — Doesn't override user with wrong product
- ✅ **Discrepancies show the issue** — Product mismatch is clear

### Key Learning
This shows the system protects against major errors:
- **Detects when search returns wrong product**
- **Doesn't blindly apply source data when it's wrong product**
- **Flags for human review instead of auto-correcting to wrong product**

---

## Comparison: Old vs New System

| Scenario | Old System Output | New System Output |
|----------|------------------|-------------------|
| **Type mismatch (EDT vs EDP)** | Accepts EDT as-is | Corrects to EDP with explanation |
| **Missing gender** | Leaves empty | Adds from source with remark |
| **Giftset components wrong** | Accepts as-is | Validates each, corrects types |
| **H&B abbreviation** | Keeps abbreviated | Expands to AZZARO WANTED SHAMPOO |
| **Source ambiguous** | Maybe High confidence | Correctly sets to Low confidence |
| **Wrong product detected** | Might apply anyway | Flags needs_review = true, doesn't correct |
| **Confidence scoring** | Might be High when unclear | Appropriately Medium/Low when unsure |
| **Audit trail** | Minimal remarks | Complete discrepancies + corrections list |

---

## Summary

The strict validator:
1. **Extracts completely from source** — All 6 fields
2. **Extracts completely from user** — All 5 fields  
3. **Compares field-by-field** — No field is missed
4. **Uses source as truth** — Not user input
5. **Corrects based on source** — Not guessing
6. **Provides audit trail** — Every decision documented
7. **Assigns confidence correctly** — High when source clear, Low when ambiguous
8. **Flags for review appropriately** — Doesn't guess when unsure
9. **Handles special cases** — Giftsets, non-fragrance, product mismatch

