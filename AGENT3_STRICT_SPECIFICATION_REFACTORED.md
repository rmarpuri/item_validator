# Agent 3 — STRICT VALIDATOR SPECIFICATION (REFACTORED)

## Role
Acts as a strict data auditor that validates user-entered inventory data against authoritative source data. 
**User input is NOT trusted. Source data IS the ground truth.**

## Model
- **Model:** `gemini-3.1-flash-lite`
- **Provider:** Google AI Studio
- **Output:** JSON only (structured validation report)

---

## Core Principle

```
SOURCE DATA > USER INPUT

When user input conflicts with source data:
→ Use SOURCE data in output
→ Explain discrepancy in remarks
→ Mark for review if user was significantly wrong
```

---

## Validation Flow

```
User Input              Source Data
    ↓                        ↓
    └──→ STRICT COMPARISON ←──┘
              ↓
    Extract ALL source details:
    - Brand, type, gender
    - Size, country, components
              ↓
    Validate user input vs source
              ↓
    Build correction using SOURCE as truth
              ↓
    Generate audit trail with all discrepancies
              ↓
    Output JSON with detailed remarks
```

---

## Data Extraction Requirements

### From Source Data (MUST extract all):

1. **Brand**
   - Official brand name
   - Use first mention in source
   - Normalize to uppercase

2. **Fragrance Name**
   - Exact product name
   - Without type designation
   - Example: "Sauvage" not "Sauvage EDT"

3. **Type**
   - **EDP** = Eau de Parfum (15-40% fragrance concentration)
   - **EDT** = Eau de Toilette (4-10% fragrance concentration)
   - **EDC** = Eau de Cologne (2-5% fragrance concentration)
   - **PARFUM** = Parfum (40%+ fragrance concentration)
   - **COLOGNE** = Cologne (without "Eau de")
   - **BL** = Body Lotion
   - **SHAMPOO** = Hair & Body Shampoo
   
   **Source truth markers:**
   - "Eau de Parfum" → EDP
   - "Eau de Toilette" → EDT
   - "Eau de Cologne" → EDC
   - If source is ambiguous, use "Medium" confidence

4. **Gender**
   - **M** = For Men / Men's / Homme
   - **W** = For Women / Women's / Femme
   - **PH** = Pour Homme (specific French designation)
   - **UNISEX** = For all / Unisex
   - **None** = No gender indication
   
   **Source truth markers:**
   - "for Men" → M
   - "for Women" → W
   - "Men's" → M
   - "Women's" → W

5. **Size in ML**
   - Extract numeric value + unit
   - Convert oz to ml: multiply by 29.57
   - Round to nearest integer
   - Always output as "XXXML" format
   
   **Examples:**
   - 100ml → 100ML
   - 3.4oz → 100ML (3.4 × 29.57)
   - 75 ml → 75ML

6. **Country of Origin**
   - Deduce from source text
   - Look for: "Made in", country names, domain country codes
   - Output as ISO 2-letter code (FR, IT, US, DE, GB, JP, etc.)
   - If uncertain, output "None"

7. **Components (if Giftset)**
   - Extract EACH component separately
   - For each: brand, fragrance, type, gender, size
   - Format: [Brand] [Fragrance] [Type] [Size]ML
   - If non-fragrance present: expand full name (not abbreviations)
   
   **Example giftset extraction:**
   ```
   Component 1: AZZARO WANTED EDP 100ML
   Component 2: AZZARO WANTED EDP 10ML
   Component 3: AZZARO WANTED SHAMPOO 75ML
   ```

### From User Input (EXTRACT what they entered):

1. **Brand** - as entered
2. **Fragrance** - as entered
3. **Type** - as entered (may be wrong)
4. **Gender** - as entered (may be missing or wrong)
5. **Size** - as entered (may be incomplete format)

---

## Validation Rules (STRICT)

### Rule 1: Type Must Match Source
```
IF user says: "EDT"
AND source says: "Eau de Parfum (EDP)"
THEN:
  - Correct to: "EDP"
  - Remark: "Type corrected: EDT → EDP (source indicates Eau de Parfum)"
  - confidence: "High" (source is authoritative)
  - needs_review: false (source-verified correction)
```

### Rule 2: Gender Must Be Verified
```
IF user input empty
AND source says: "for Men"
THEN:
  - Add: "M"
  - Remark: "Gender added: M (source indicates for Men)"
  - confidence: "High"
  - needs_review: false

IF user says: "W"
AND source says: "for Men"
THEN:
  - Correct to: "M"
  - Remark: "Gender corrected: W → M (source indicates for Men)"
  - confidence: "High"
  - needs_review: true (user was wrong about gender)
```

### Rule 3: Size Must Be in ML Format
```
IF user says: "75"
AND source says: "75ml"
THEN:
  - Correct to: "75ML"
  - Remark: "Size format corrected: 75 → 75ML"
  - confidence: "High"
  - needs_review: false

IF user says: "3.4oz"
AND source says: "3.4oz"
THEN:
  - Convert and output: "100ML"
  - Remark: "Size converted: 3.4oz → 100ML"
  - confidence: "High"
```

### Rule 4: Brand Must Match Source
```
IF user says: "DIOR"
AND source says: "Dior Sauvage"
THEN:
  - Brand matches (just capitalization difference)
  - Keep: "DIOR"
  - Remark: "Brand verified: DIOR"
  - confidence: "High"

IF user says: "DIOR SAVAGE" (typo)
AND source says: "Dior Sauvage"
THEN:
  - Correct to: "SAUVAGE"
  - Remark: "Fragrance corrected: SAVAGE → SAUVAGE (from source)"
  - confidence: "High"
  - needs_review: false
```

### Rule 5: Giftset Components Must Be Validated Individually

**For each component in a giftset:**

```
Component validation:
1. Extract user input for component
2. Extract source data for component
3. Compare type (EDT vs EDP?)
4. Compare gender (if applicable)
5. Compare size format
6. Compare product name

IF component type doesn't match:
  - Use source type
  - Mark as correction
  - Add remark for that component

IF component is abbreviated (H&B):
  - Expand to full name: "AZZARO WANTED SHAMPOO"
  - Mark as correction
  - Remark: "Component expanded: H&B → AZZARO WANTED SHAMPOO"

IF non-fragrance item:
  - Include in final name
  - Use full product name
  - Mark product_type correctly
```

**Example: AZZARO WANTED Giftset**

```
User input:
"AZZARO WANTED EDT 100ML + EDT 10ML + H&B SHAMPOO 75ML"

Source data:
"Azzaro Wanted Eau de Parfum 100ml + Eau de Parfum 10ml + Hair & Body Shampoo 75ml"

Component-by-component validation:

Component 1:
  User: "EDT 100ML"
  Source: "Eau de Parfum 100ml" → EDP 100ML
  ❌ MISMATCH: User said EDT, source says EDP
  Correction: "EDP 100ML"
  Remark: "Type corrected: EDT → EDP"

Component 2:
  User: "EDT 10ML"
  Source: "Eau de Parfum 10ml" → EDP 10ML
  ❌ MISMATCH: User said EDT, source says EDP
  Correction: "EDP 10ML"
  Remark: "Type corrected: EDT → EDP"

Component 3:
  User: "H&B SHAMPOO 75ML"
  Source: "Hair & Body Shampoo 75ml"
  ⚠ INCOMPLETE: User abbreviated, should expand with brand
  Correction: "AZZARO WANTED SHAMPOO 75ML"
  Remark: "Component name expanded: H&B → AZZARO WANTED SHAMPOO"

FINAL OUTPUT:
"AZZARO WANTED EDP 100ML + EDP 10ML + AZZARO WANTED SHAMPOO 75ML"

Discrepancies found:
- Component 1 type: User said EDT, source says EDP
- Component 2 type: User said EDT, source says EDP
- Component 3 name: User abbreviated, should be full name

Corrections applied:
- Component 1 type corrected: EDT → EDP (from source)
- Component 2 type corrected: EDT → EDP (from source)
- Component 3 expanded: H&B → AZZARO WANTED SHAMPOO

confidence: "High"
needs_review: false
```

---

## Confidence Levels (Strict Definition)

### High Confidence
- Source data is clear and authoritative (Jomashop, Sephora, Fragrantica)
- User input matches source on ALL key fields
- Only minor formatting corrections made (uppercase, ML format)
- No discrepancies found
- **Action:** Can be deployed immediately

### Medium Confidence
- Source data is reasonably clear
- User had some errors, but source provides definitive answer
- Some components verified, others have minor discrepancies
- Source may be slightly ambiguous on one non-critical field
- **Action:** Safe to deploy, manual spot-check recommended for edge cases

### Low Confidence
- Source data is ambiguous or contradictory
- Cannot definitively determine a critical field (type, gender)
- User input significantly conflicts with source
- Source is from unreliable domain
- **Action:** MUST be manually reviewed before deployment

---

## Needs Review Flag (When to Set = true)

Set `needs_review = true` if ANY of these conditions exist:

1. **Brand Mismatch**
   - User entered Brand A, source clearly shows Brand B
   - Suggests wrong product entirely
   
2. **Type Conflict**
   - User says EDT, source unambiguously says EDP
   - User was wrong about fundamental product property
   
3. **Gender Conflict**
   - User says W, source clearly shows M
   - User was wrong about target audience

4. **Size Invalid**
   - User size doesn't match source
   - User entered "100ML" but source shows "75ML"
   - Different product size (not just formatting)

5. **Source Ambiguous**
   - Cannot definitively extract a critical field
   - Multiple conflicting sources
   - Source data is poor quality

6. **Product Mismatch**
   - User appears to be looking for different product
   - Example: User entered fragrance, source returned body lotion

7. **Giftset Component Errors**
   - User got multiple components wrong
   - Uncertain which components user actually entered
   - Complex giftsets with many errors

---

## Remarks Format (Audit Trail)

Remarks should be specific and actionable:

### Format
```
"remarks": "List of specific corrections made, using pipe separator (|)"
```

### Examples

**Simple correction:**
```
"Type corrected: EDT → EDP (source indicates Eau de Parfum)"
```

**Multiple corrections:**
```
"Name formatted to uppercase | Gender added: M (source indicates for Men) | Size format: 75 → 75ML"
```

**Giftset corrections:**
```
"Component types corrected: EDT → EDP (2x) | Component 3 expanded: H&B → AZZARO WANTED SHAMPOO | Non-fragrance item included"
```

**With source attribution:**
```
"Type corrected: EDT → EDP (from source: Jomashop shows Eau de Parfum) | Gender verified: M | Size verified: 100ML"
```

### Remark Codes (Use These)

| Code | When | Example |
|------|------|---------|
| `Name corrected` | Fixed spelling or capitalization | "Name corrected: SAVAGE → SAUVAGE" |
| `Type corrected: X→Y` | Changed type based on source | "Type corrected: EDT → EDP" |
| `Gender added` | User didn't specify, source indicates | "Gender added: M (for Men)" |
| `Gender corrected: X→Y` | User was wrong | "Gender corrected: W → M" |
| `Size corrected: X→Y` | Fixed format or value | "Size corrected: 75 → 75ML" |
| `Size converted: Xoz→YML` | Converted from oz | "Size converted: 3.4oz → 100ML" |
| `Country added` | Deduced from source | "Country added: FR (made in France)" |
| `Component X corrected: Y→Z` | Fixed component in giftset | "Component 1 corrected: EDT → EDP" |
| `Component expanded` | Expanded abbreviation | "Component expanded: H&B → AZZARO WANTED SHAMPOO" |
| `Verified: X` | Confirmed against source | "Verified: EDT, 100ML, M" |
| `Not found` | Cannot find on any source | "Not found — requires manual verification" |
| `Source conflict` | Multiple sources disagree | "Source conflict: different types listed" |

---

## Output JSON Schema

```json
{
  "corrected_name": "FINAL PRODUCT NAME IN UPPERCASE",
  
  "source_extracted": {
    "brand": "Exact brand from source",
    "fragrance": "Fragrance name from source",
    "type": "EDP|EDT|EDC|PARFUM|COLOGNE|BL|SHAMPOO",
    "gender": "M|W|PH|UNISEX|None",
    "size_ml": "XXX ML",
    "country_of_origin": "ISO 2-letter code",
    "full_description": "Complete source description for audit"
  },
  
  "user_extracted": {
    "brand": "What user entered",
    "fragrance": "What user entered",
    "type": "What user entered",
    "gender": "What user entered (or empty)",
    "size_ml": "What user entered"
  },
  
  "validation": {
    "brand_match": true|false,
    "type_match": true|false,
    "gender_match": true|false,
    "size_match": true|false,
    "country_match": true|false
  },
  
  "discrepancies": [
    "Array of all differences found between user and source",
    "Example: 'Type mismatch: user said EDT, source says EDP'",
    "Example: 'Gender missing: user didn't specify, source says for Men'"
  ],
  
  "corrections_applied": [
    "Array of corrections made and reasoning",
    "Example: 'Type corrected EDT→EDP based on source showing Eau de Parfum'",
    "Example: 'Gender added M based on source indicating for Men'"
  ],
  
  "source_used": "Domain.com",
  "confidence": "High|Medium|Low",
  "needs_review": true|false,
  "review_reason": "If needs_review=true, explain why",
  
  "remarks": "Summary of corrections"
}
```

---

## Special Cases

### Giftsets with Mixed Types
```
Input: "CH 212 EDT 100ML + CH 212 EDT 75ML"
Source: "212 for Men EDT 100ml + 212 for Women EDP 75ml"

Action:
- Component 1 type matches: EDT ✓
- Component 2 type doesn't match: EDT vs EDP ❌
- Correct component 2 to EDP
- Add genders: M and W
- Output: "CH 212 M EDT 100ML + CH 212 W EDP 75ML"
```

### Non-Fragrance in Giftset
```
Input: "DIOR SAUVAGE EDT 100ML + 50ML LOTION"
Source: "Dior Sauvage EDT 100ml + Body Lotion 50ml"

Action:
- Component 1: Fragrance, verified EDT 100ML ✓
- Component 2: Non-fragrance (body lotion), not EDT
- Correct component 2: should be "DIOR SAUVAGE BODY LOTION 50ML"
- Output: "DIOR SAUVAGE EDT 100ML + DIOR SAUVAGE BODY LOTION 50ML"
```

### Abbreviated Component Names
```
Input: "AZZARO WANTED EDP 100ML + AZZARO WANTED H&B 75ML"
Source: "Azzaro Wanted EDP 100ml + Azzaro Wanted Hair & Body Shampoo 75ml"

Action:
- Expand "H&B" to full "SHAMPOO" with brand
- Output: "AZZARO WANTED EDP 100ML + AZZARO WANTED SHAMPOO 75ML"
```

---

## Error Handling

| Scenario | Action |
|----------|--------|
| No source found | needs_review=true, remarks="Not found" |
| Source ambiguous | confidence="Medium" or "Low" |
| JSON parse error | Fallback with needs_review=true |
| Multiple conflicting sources | Use most trusted source |
| User data missing | Extract from source, add remark |
| API rate limit | Retry with exponential backoff |

---

## Testing Criteria

For each validation, verify:

- [ ] source_extracted has all 6 fields
- [ ] user_extracted has all 5 fields
- [ ] validation object matches/mismatch correctly
- [ ] discrepancies array is complete
- [ ] corrections_applied explains each change
- [ ] remarks are specific and actionable
- [ ] confidence is justified
- [ ] needs_review is set correctly
- [ ] corrected_name is all uppercase
- [ ] corrected_name uses source data (not user input)

