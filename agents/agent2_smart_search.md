# Agent 2 — Smart Search Agent

## Role
For every inventory item, searches for authoritative product data across
multiple trusted fragrance and retail websites using the Serper API (Google Search).
Returns ranked, deduplicated results with trust scores for Agent 3 to validate against.

## Responsibility
- Execute a 3-pass search strategy: Jomashop → Trusted Retailers → Fragrantica/Broad
- Score each result source by reliability using the Trust Score System
- Deduplicate results across domains — keep best result per domain
- Format results with clear trust labels so Agent 3 can make informed decisions
- Fall back gracefully when no trusted sources are found

## Input
- `item_name`: product name string extracted from the CSV row
- `SERPER_API_KEY` from environment

## Output
Formatted string with up to 6 results ranked by trust score (highest first).
Each result includes: title, source domain, trust label, URL, snippet.

## Search Strategy — 3 Passes

### Pass 1 — Jomashop (Primary Source)
```
Query: site:jomashop.com {item_name}
```
- Jomashop is the company's primary reference site
- If results with trust score ≥ 8 found → stop, return these results only
- Saves API quota for items found on Jomashop

### Pass 2 — Trusted Fragrance Retailers
Triggered only if Pass 1 returns no trusted results.
```
Query: {item_name} perfume EDP EDT ml
       site:fragrancenet.com OR site:sephora.com OR site:nordstrom.com
       OR site:fragrancex.com OR site:perfumania.com
```
- Any result with trust score ≥ 7 is included

### Pass 3 — Fragrantica + Broad Search
Runs alongside Pass 2 when Jomashop misses.
```
Query: {item_name} perfume fragrance EDP EDT ml
```
- Catches Fragrantica (score 9) — best source for gender, concentration
- Also catches any other trusted sites in broad results

### Fallback — Any Source
Only if Passes 1–3 yield nothing trusted.
```
Query: {item_name} perfume
Query: {item_name} fragrance
```
- Includes all results regardless of trust score
- Agent 3 will flag these as `needs_review = true`

## Trust Score System

| Score | Trust Level    | Label                | Sites |
|-------|---------------|----------------------|-------|
| 10    | Primary        | ★★★ HIGHLY TRUSTED  | jomashop.com |
| 9     | Highly Trusted | ★★★ HIGHLY TRUSTED  | sephora.com, nordstrom.com, fragrancenet.com, fragrantica.com, Google Knowledge Graph |
| 8     | Trusted        | ★★  TRUSTED         | macys.com, bloomingdales.com, fragrancex.com, perfumania.com, basenotes.net |
| 7     | Trusted        | ★★  TRUSTED         | feelunique.com, parfumo.com |
| 4–6   | Moderate       | ★   MODERATE        | Other recognisable retail sites |
| 0–3   | Unknown        | UNKNOWN SOURCE      | Blogs, forums, unverified sites |

## Deduplication
- Results grouped by domain, highest trust per domain kept
- Final list sorted by trust score descending
- Max 6 results passed to Agent 3

## API Usage
| Resource | Limit | Strategy |
|----------|-------|----------|
| Serper free tier | 100/day = 3,000/month | Pass 1: 1 call; Pass 2+3: 2 more only on miss |
| Per item (Jomashop hit) | 1 call | ~80% of items |
| Per item (Jomashop miss) | 3 calls max | ~20% of items |

## Dependencies
- `requests`
- `urllib.parse` (standard library)
- Environment: `SERPER_API_KEY`
