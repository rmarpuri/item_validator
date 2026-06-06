# Prompt Engineering Guide — Strict Validator System

## Overview

This guide explains the prompt engineering philosophy and techniques used in the refactored strict validator system.

---

## Problem Statement

**The Old Approach:**
- User input was treated as semi-authoritative
- Minor discrepancies were overlooked
- Component types weren't validated strictly
- Non-fragrance items were abbreviated or ignored
- Source data was used for "verification" not "correction"

**Why It Failed:**
- Users entered "EDT" when source clearly said "Eau de Parfum (EDP)"
- User input errors weren't corrected, just annotated
- Confidence was high even when user was demonstrably wrong

**The New Approach:**
- Source data is THE TRUTH
- User input is validated AGAINST source data
- Every discrepancy is identified and corrected
- User errors result in appropriate needs_review flag

---

## Core Prompt Engineering Principles

### Principle 1: Establish Clear Authority

**BEFORE (Ambiguous):**
```
"Examine search text payload fields to deduce the country..."
```

**AFTER (Clear):**
```
"The SOURCE DATA is the ground truth. User input is fallible and must be validated.
PRINCIPLE: SOURCE DATA > USER INPUT ALWAYS"
```

**Why:** Removes ambiguity about whose data takes priority. Gemini now knows explicitly that source wins every time.

---

### Principle 2: Explicit Extraction Instructions

**BEFORE (Vague):**
```
"Return structural JSON only"
```

**AFTER (Detailed):**
```
"You MUST extract from source data:
- Product name (exact)
- Brand (official)
- Type (from description: EDP/EDT/etc.)
- Gender (M/W/Unisex/None)
- Size (in ML)
- Country (deduced from source)
- Components (if giftset)"
```

**Why:** Eliminates guessing. Gemini knows exactly what to extract and how.

---

### Principle 3: Source Truth Markers

**BEFORE (Implicit):**
```
"Examine search text payload fields..."
```

**AFTER (Explicit Mappings):**
```
"Type validation:
- 'Eau de Parfum' = EDP
- 'Eau de Toilette' = EDT
- 'Eau de Cologne' = EDC

Gender validation:
- 'for Men' → M
- 'for Women' → W
- 'Men's' → M
- 'Women's' → W"
```

**Why:** No ambiguity about how to interpret source data. Gemini has explicit mapping rules.

---

### Principle 4: Comparison Logic (Not Just Extraction)

**BEFORE (No comparison):**
```
"User input..."
"Source data..."
"Output JSON"
```

**AFTER (Explicit comparison steps):**
```
"3. VALIDATE EACH FIELD:
   For brand, type, gender, size, country:
   a) Is user input present?
   b) Does it match source data?
   c) If no match: use source data, mark as correction
   d) If match: confirm, mark as verified"
```

**Why:** Forces step-by-step validation instead of lazy acceptance of user data.

---

### Principle 5: Conflict Resolution Rules

**BEFORE (Vague):**
```
"For giftsets, intensely verify the EDP vs EDT status..."
```

**AFTER (Specific):**
```
"IF user says: 'EDT'
AND source says: 'Eau de Parfum (EDP)'
THEN:
- Correct to: 'EDP'
- Remark: 'Type corrected: EDT → EDP (from source)'
- confidence: 'High'
- needs_review: false"
```

**Why:** No ambiguity about what to do in conflicts. Gemini follows exact rules.

---

### Principle 6: Detailed Output Structure

**BEFORE (Minimal):**
```
{
  "corrected_name": "...",
  "remarks": "...",
  "confidence": "..."
}
```

**AFTER (Detailed for Audit):**
```
{
  "corrected_name": "...",
  "source_extracted": { all 6 fields },
  "user_extracted": { all 5 fields },
  "validation": { match status for each field },
  "discrepancies": [ all differences found ],
  "corrections_applied": [ all changes with reasons ],
  "remarks": "..."
}
```

**Why:** Audit trail. Shows exactly what was compared, what differed, and why changes were made.

---

### Principle 7: Multiple Remark Types

**BEFORE (Generic):**
```
"remarks": "Name corrected"
```

**AFTER (Specific codes):**
```
"Type corrected: EDT → EDP (from source)"
"Gender added: M (source indicates for Men)"
"Component expanded: H&B → AZZARO WANTED SHAMPOO"
"Size format corrected: 75 → 75ML"
```

**Why:** Each remark type tells a story. Can be parsed programmatically for reporting.

---

## Advanced Prompt Techniques Used

### Technique 1: Hierarchy of Authority

```python
PRINCIPLE: SOURCE DATA > USER INPUT ALWAYS

In case of conflict:
→ IGNORE user input
→ USE source data  
→ EXPLAIN the discrepancy
→ Flag for review if user was significantly wrong
```

**Effect:** Gemini doesn't equivocate. Source wins, period.

---

### Technique 2: Explicit Examples

```python
"Example 1: Simple product
  User entered: "dior sauvage edt 75"
  Source says: "Dior Sauvage Eau de Toilette 75ml"
  Output: "DIOR SAUVAGE EDT 75ML"
  Remarks: "Size format corrected: 75 → 75ML"

Example 2: Wrong type
  User entered: "CHANEL NO5 EDT 100ML"
  Source says: "Chanel No. 5 Eau de Parfum 100ml"
  Output: "CHANEL NO5 EDP 100ML"
  Remarks: "Type corrected: EDT → EDP (source says Eau de Parfum)"
  
Example 4: Giftset with wrong components
  User entered: "AZZARO WANTED EDT 100ML + EDT 10ML + H&B 75ML"
  Source says: "Azzaro Wanted Eau de Parfum 100ml + Eau de Parfum 10ml + Hair & Body Shampoo 75ml"
  Output: "AZZARO WANTED EDP 100ML + EDP 10ML + AZZARO WANTED SHAMPOO 75ML"
  Remarks: "Component types corrected: EDT→EDP (2x) | Component 3 expanded"
```

**Effect:** Gemini sees examples of desired behavior and replicates them.

---

### Technique 3: Negative Examples (What NOT to do)

```python
NOT:
- "Accept user input as-is"
- "Skip validation if source matches user"
- "Abbreviate component names (H&B)"
- "Assume gender if not specified by user"

ALWAYS:
- "Extract all source details first"
- "Compare user input to each extracted field"
- "Use SOURCE data in corrected_name"
- "Add gender if source indicates it"
```

**Effect:** Clarifies boundaries. Gemini knows what failures look like.

---

### Technique 4: Confidence Rubric

```python
High Confidence:
- Source data is clear and authoritative
- User input matches source on all key fields
- Only minor formatting corrections
- Can be deployed immediately

Medium Confidence:
- Source is reasonably clear
- User had some errors, source provides answer
- Safe to deploy, manual spot-check recommended

Low Confidence:
- Source data is ambiguous
- Cannot determine critical field
- MUST be manually reviewed
```

**Effect:** Gemini knows how to assign confidence based on objective criteria, not guessing.

---

### Technique 5: Explicit Discrepancy Tracking

```python
"discrepancies": [
  "Type mismatch: user said EDT, source says EDP",
  "Gender missing: user didn't specify, source says for Men",
  "Size format: user said 75, source says 75ml"
]

"corrections_applied": [
  "Type corrected EDT→EDP based on source showing Eau de Parfum",
  "Gender added M based on source indicating for Men",
  "Size formatted 75→75ML per convention"
]
```

**Effect:** Audit trail. Can trace every decision and its reasoning.

---

### Technique 6: Giftset Component Isolation

```python
"For EACH component in a giftset:
- Extract user input for component
- Extract source data for component
- Compare type (EDT vs EDP?)
- Compare gender (if applicable)
- Compare size format
- Compare product name

IF component type doesn't match:
  - Use source type
  - Mark as correction
  - Add remark for that component"
```

**Effect:** No component is overlooked. Each is validated independently.

---

### Technique 7: Non-Fragrance Item Handling

```python
"IF non-fragrance item:
- Include in final name
- Use full product name (not abbreviations)
- Mark product_type correctly

Example:
Input: "AZZARO WANTED EDP 100ML + H&B 75ML"
Output: "AZZARO WANTED EDP 100ML + AZZARO WANTED SHAMPOO 75ML"
Remark: "Component expanded: H&B → AZZARO WANTED SHAMPOO"
```

**Effect:** Non-fragrance items are explicitly handled, not hidden.

---

## Prompt Structure

The strict validator prompt follows this structure:

```
1. ROLE & AUTHORITY STATEMENT
   ├─ What you are (data auditor)
   ├─ What's authoritative (source data)
   └─ What principle governs you (source > user)

2. EXPLICIT EXTRACTION RULES
   ├─ What to extract from source
   ├─ How to interpret source
   └─ Exact mapping rules (EDT, EDP, etc.)

3. COMPARISON PROCEDURE
   ├─ Extract from both sources
   ├─ Compare field-by-field
   ├─ Identify discrepancies
   └─ Apply source truth

4. DETAILED EXAMPLES
   ├─ Simple product example
   ├─ Type mismatch example
   ├─ Giftset example
   └─ Non-fragrance example

5. OUTPUT SCHEMA
   ├─ Required fields
   ├─ Data structure
   └─ Remark format

6. CONFIDENCE RUBRIC
   ├─ High confidence criteria
   ├─ Medium confidence criteria
   └─ Low confidence criteria

7. NEEDS_REVIEW CRITERIA
   ├─ When to flag for review
   ├─ What triggers review
   └─ Specific scenarios
```

---

## Key Differences: Old vs New Prompt

### Old Prompt
```
Short: "You are a perfume validation bot. Return structural JSON only."
Vague: "Examine search text payload fields"
Passive: "Intensely verify"
Implicit: Assumes Gemini knows what matters
```

### New Prompt
```
Long: ~1200 lines of detailed instruction
Specific: "You MUST extract from source: brand, type, gender, size, country, components"
Active: "Compare user input to source field-by-field"
Explicit: Every rule, every example, every decision point specified
```

---

## Why This Matters

### Old System Output
```
User enters: "AZZARO WANTED EDT 100ML + EDT 10ML"
Source shows: "Eau de Parfum + Eau de Parfum"
Old output: "AZZARO WANTED EDT 100ML + EDT 10ML" ❌ WRONG
Confidence: "High" (misleading)
```

### New System Output
```
User enters: "AZZARO WANTED EDT 100ML + EDT 10ML"
Source shows: "Eau de Parfum + Eau de Parfum"
New output: "AZZARO WANTED EDP 100ML + EDP 10ML" ✅ CORRECT
Confidence: "High" (justified)
Remarks: "Component types corrected: EDT→EDP (2x, from source)"
Discrepancies: ["Type mismatch: user said EDT, source says EDP (2x)"]
```

---

## Testing the Prompt

To verify the prompt is working correctly, test with these scenarios:

1. **Type Mismatch** - User says EDT, source says EDP
   - Expected: Corrects to EDP
   - Verify: Remarks explain why

2. **Missing Gender** - User omits gender, source shows M
   - Expected: Adds M from source
   - Verify: Confidence is High

3. **Giftset Components** - User gets components wrong
   - Expected: Each component corrected
   - Verify: discrepancies array has all mismatches

4. **Non-Fragrance Item** - User abbreviates (H&B)
   - Expected: Expands to full name
   - Verify: Remarks explain expansion

5. **Size Format** - User says "75", source says "75ml"
   - Expected: Outputs "75ML"
   - Verify: Remark mentions format correction

---

## Maintenance & Evolution

The prompt should be reviewed and updated if:

1. **New product types emerge** (e.g., eau fraîche)
   - Add to extraction rules
   - Add to examples
   - Add to validation rules

2. **New giftset formats** (e.g., 3-component sets)
   - Add to component isolation section
   - Add example
   - Update output schema if needed

3. **New source formats** (e.g., subscription boxes)
   - Add extraction markers
   - Add to examples
   - Update procedure section

4. **Validation failures occur**
   - Review failed cases
   - Identify missing rules
   - Add explicit rule or example
   - Re-test

---

## Summary

The strict validator prompt achieves accuracy through:

✅ **Clear authority** - Source data always wins
✅ **Explicit extraction** - Know exactly what to extract
✅ **Detailed comparison** - Field-by-field validation
✅ **Rich examples** - See desired behavior
✅ **Audit trail** - Track all decisions
✅ **Confidence rubric** - Objective confidence assignment
✅ **Detailed output** - Full transparency

This is not a simple prompt. It's a comprehensive specification written in natural language that Gemini can understand and follow precisely.

