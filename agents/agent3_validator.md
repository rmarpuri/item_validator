# Agent 3 — Validation Agent (Gemini 3.1 Flash Lite)

## Role
Uses Google Gemini 3.1 Flash Lite to validate each inventory item against trusted web sources,
apply the company naming convention strictly, and return a structured JSON result.

## Model
- **Model:** `gemini-3.1-flash-lite`
- **Provider:** Google AI Studio
- **Tier:** Free (1,500 req/day, 15 RPM)
- **Output:** JSON only, max 400 tokens per call

---

## NAMING CONVENTION — STRICT RULES

### Universal Rules (apply to ALL product types)
1. **ALL UPPERCASE** — every single character in `corrected_name` must be uppercase
2. **ML suffix** — size must always end with `ML` (e.g. `100ML`, `50ML`, `7.5ML`)
3. **Valid types** — `EDP`, `EDT`, `EDC`, `PARFUM`, `COLOGNE` only
4. **Valid genders** — `M`, `W`, `PH`, `UNISEX` only
5. **Brand abbreviations** — apply these always:
   - `DOLCE & GABBANA` / `DOLCE AND GABBANA` → `D&G`
   - `JEAN PAUL GAULTIER` → `JPG`
   - `CAROLINA HERRERA` → `CH`
6. **Never change the product** — if search results do not match the entered item, set `needs_review = true`
7. **Do not change brand or fragrance** — if the validated/corrected brand or fragrance differs
   from the employee-entered item such that it would represent a different product, return
   `needs_review = true` and include the remark: `Brand mismatch — manual review`.

---

### Product Type Rules

#### Standard Product
```
Format : [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML
Example: CHANEL BLEU DE CHANEL EDP 100ML
         DIOR SAUVAGE EDT 75ML
         YSL BLACK OPIUM EDP 90ML
```

---

#### VIAL
```
Format  : [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML VIAL
Suffix  : Name MUST end with VIAL
Size    : MUST be less than 5ML
Examples: CHANEL NO5 EDP 2ML VIAL
          DIOR SAUVAGE EDT 1.5ML VIAL
```
**Rules:**
- If name does NOT end with `VIAL` → add it → remark: `Vial name corrected`
- If size is 5ML or more → remark: `Vial size invalid` + `needs_review = true`

---

#### MINI
```
Format  : [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML MINI
Suffix  : Name MUST end with MINI
Size    : MUST be between 5ML and 12ML (inclusive)
Examples: CHANEL BLEU EDP 10ML MINI
          YSL BLACK OPIUM EDP 7.5ML MINI
```
**Rules:**
- If name does NOT end with `MINI` → add it → remark: `Mini name corrected`
- If size < 5ML or > 12ML → remark: `Mini size invalid` + `needs_review = true`

---

#### MINI SET
```
Format  : [BRAND] [FRAGRANCE NAME] [TYPE] [QTY] X [SIZE]ML MINI SET
Suffix  : Name MUST end with MINI SET
Examples: JPG LE MALE EDT 4 X 7ML MINI SET
          DIOR SAUVAGE EDT 3 X 10ML MINI SET
```
**Rules:**
- If name does NOT end with `MINI SET` → add it → remark: `Mini set name corrected`
- ALL uppercase including quantity and X

---

#### TESTER
```
Format  : [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE]ML TESTER
Suffix  : Name MUST end with TESTER
Examples: CREED AVENTUS EDP 100ML TESTER
          VERSACE EROS EDT 100ML TESTER
          AB HER GOLDEN SECRET EDT 80ML TESTER
```
**Rules:**
- If name does NOT end with `TESTER` → add it → remark: `Tester name corrected`

---

#### GIFT SET — Same Fragrance
```
Format  : [BRAND] [FRAGRANCE NAME] [TYPE] [SIZE1]ML + [SIZE2]ML (+ [SIZE3]ML ...)
Rule    : Do NOT include the words GIFTSET or GIFT SET anywhere
Rule    : List ONLY the component sizes after the product name, separated by +
Examples: CHANEL NO5 EDP 100ML + 50ML
          DIOR SAUVAGE EDP 100ML + 10ML + 50ML
```
**Rules:**
- Remove any occurrence of `GIFTSET` or `GIFT SET` from name → remark: `Giftset format corrected`
- Sizes listed after fragrance name with ` + ` separator

---

#### GIFT SET — Different Fragrances
```
Format  : [BRAND] [FRAGRANCE1 SHORT] [SIZE1]ML + [BRAND] [FRAGRANCE2 SHORT] [SIZE2]ML
Rule    : Do NOT include the words GIFTSET or GIFT SET anywhere
Rule    : Each component = SHORT FRAGRANCE NAME + SIZE
Examples: CH 212 M EDT 100ML + CH 212 W EDP 75ML
          D&G LIGHT BLUE M EDT 75ML + D&G LIGHT BLUE W EDT 50ML
```
**Rules:**
- Remove any occurrence of `GIFTSET` or `GIFT SET` → remark: `Giftset format corrected`
- Each component separated by ` + `

---

## Source Trust Hierarchy

| Priority | Label | Sources |
|----------|-------|---------|
| 1st | ★★★ HIGHLY TRUSTED | Jomashop, Sephora, Nordstrom, Fragrantica, Knowledge Graph |
| 2nd | ★★  TRUSTED | FragranceNet, FragranceX, Perfumania, Bloomingdales, Macys |
| 3rd | ★   MODERATE | Other recognisable retail sites |
| Last | UNKNOWN | Blogs, forums — do not trust for facts |

---

## Confidence Assignment

| Condition | Confidence | needs_review |
|-----------|-----------|--------------|
| 2+ highly trusted sources agree | High | false |
| 1 highly trusted source found | High | false |
| Only trusted (score 7–8) sources | Medium | false |
| Sources conflict on key field | Medium | true |
| Only moderate/unknown sources | Low | true |
| No sources found | Low | true |
| JSON/API error | Low | true |

---

## Remark Codes

Use these exact codes, combined with ` | ` for multiple issues.

| Code | When to use | Example |
|------|------------|---------|
| `OK` | Entry is exactly correct | `OK` |
| `Name corrected` | Name was wrong or lowercase | `Name corrected` |
| `Type corrected: X→Y` | Wrong EDP/EDT type | `Type corrected: edt→EDP` |
| `Size corrected: XML→YML` | Wrong size or missing ML | `Size corrected: 100→100ML` |
| `Gender added` | Gender was missing | `Gender added` |
| `Vial name corrected` | Missing VIAL suffix | `Vial name corrected` |
| `Vial size invalid` | Vial ≥ 5ML | `Vial size invalid` |
| `Mini name corrected` | Missing MINI suffix | `Mini name corrected` |
| `Mini size invalid` | Mini outside 5–12ML range | `Mini size invalid` |
| `Mini set name corrected` | Missing MINI SET suffix | `Mini set name corrected` |
| `Tester name corrected` | Missing TESTER suffix | `Tester name corrected` |
| `Giftset format corrected` | Had GIFTSET word / wrong format | `Giftset format corrected` |
| `Not found — manual review` | Cannot verify on any trusted source | `Not found — manual review` |

---

## JSON Output Format

```json
{
  "corrected_name": "DIOR SAUVAGE EDT 75ML",
  "brand":          "DIOR",
  "fragrance":      "SAUVAGE",
  "size_ml":        "75ML",
  "type":           "EDT",
  "gender":         "M",
  "product_type":   "Standard|Vial|Mini|Mini Set|Tester|Giftset",
  "source_used":    "jomashop.com",
  "remarks":        "Name corrected | Size corrected: 75→75ML",
  "confidence":     "High",
  "needs_review":   false
}
```

---

## Validation Decision Flow

```
1. Read all search results — note trust scores
2. Determine if search matches the entered product
   └── No match → needs_review = true, remarks = "Not found — manual review"
3. Identify product type: Standard / Vial / Mini / Mini Set / Tester / Giftset
4. Apply type-specific suffix and size rules
5. Apply universal rules: UPPERCASE, ML suffix, brand abbreviations, valid type
6. Build corrected_name in correct format for that product type
7. Generate remark codes for every correction made
8. Assign confidence based on source quality
9. Return JSON
```

---

## Error Handling

| Error | Action |
|-------|--------|
| JSON decode error | Return fallback with `remarks = "Parse error — manual review"`, `confidence = "Low"`, `needs_review = true` |
| API 429 rate limit | Wait 4s, retry once; else return fallback |
| API 500/503 | Return fallback, log error |
| Any exception | Return fallback, log full exception |

---

## Dependencies
- `google-generativeai`
- Environment: `GEMINI_API_KEY`
