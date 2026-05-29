---
name: car-search
description: Search the internet for used cars across multiple sources including non-traditional listings (Craigslist, eBay, Facebook Marketplace, dealer sites). Use when the user wants to find used cars by brand, model, year, price, or distance from a zip code. Works in Claude Code on the web using WebSearch. Returns real listings sorted by best value.
---

# Used Car Search Skill

Uses WebSearch to find real individual car listings across traditional and non-traditional
sources. Works in Claude Code on the web — no local install required.

## Step 1 — Parse parameters

Extract from the user's request:
- `make` – e.g. Hyundai, Toyota, Ford
- `model` – e.g. Tucson, Camry, F-150
- `year_min` / `year_max` – default to last 5 years if not specified
- `zip` – required; ask the user if missing
- `city` – nearest major city to the zip (e.g. zip 33160 → Miami)
- `state` – state abbreviation (e.g. FL)
- `radius` – miles from zip, default 100
- `max_price` – optional price ceiling in USD
- `max_odometer` – optional odometer ceiling in miles
- `trim` – optional trim filter; "SEL or higher" for Hyundai = SEL, Limited, N-Line, Calligraphy, Ultimate

## Step 2 — Run all searches in parallel

Fire ALL of the following WebSearch calls **simultaneously** (in one message).
Use the user's actual parameters in each query.

### Search 1 — General listings near zip
```
{year_min}-{year_max} {make} {model} {trim} used under ${max_price} near {zip} {city} {state} for sale
```

### Search 2 — Craigslist
```
{year_min} {make} {model} {trim} site:craigslist.org {city} {state} used
```

### Search 3 — eBay Motors
```
{year_min}-{year_max} {make} {model} {trim} used for sale site:ebay.com under {max_price}
```

### Search 4 — Facebook Marketplace
```
{make} {model} {trim} {year_min} used for sale site:facebook.com/marketplace {city} {state}
```

### Search 5 — Non-aggregator dealer inventory
```
"{year_min} {make} {model}" "{trim}" used for sale "${}" miles {city} {state} -cargurus.com -cars.com -autotrader.com -truecar.com
```

### Search 6 — Private sellers + small lots
```
"{make} {model}" "{trim}" {year_min} used sale price mileage {city} {state} eBay OR craigslist OR offerup OR "for sale by owner"
```

### Search 7 — Individual dealer inventory pages
```
{year_min} {make} {model} {trim} used for sale {city} dealer inventory inurl:inventory OR inurl:used-cars
```

## Step 3 — Fetch top individual listing pages

For any specific individual listing URLs that appear in search results (dealer pages, eBay item pages, Craigslist posts), use WebFetch to extract full details:
- Price, mileage, year, trim, VIN, color
- Dealer/seller name, address, phone
- Direct listing URL

Run up to 5 WebFetch calls in parallel on the most promising URLs.

## Step 4 — Compile, filter, and rank

Combine all results. For each listing:
1. Apply trim filter — drop listings that don't match requested trim level
2. Apply max_price filter — drop listings above budget
3. Apply max_odometer filter if specified
4. Score: `0.6 × (price/100000) + 0.4 × (miles/300000)` — lower is better
5. Listings missing price go to bottom; missing miles ranked by price only
6. Deduplicate by (title + price)

## Step 5 — Present results

Output:

```
## Results: {N} listings · {make} {model} {trim} · {year_min}–{year_max} · near {zip}

| # | Source | Title | Price | Miles | Location | Link |
|---|--------|-------|-------|-------|----------|------|
...

## Top 3 Picks
**#1 — [Title]** · $X,XXX · XX,XXX mi · [Source]
[Dealer/Seller] · [City]
[Direct URL]
Why: [one line — e.g. "Lowest price found, only 9k miles, CPO warranty included"]

**#2 ...**
**#3 ...**

## Budget reality check (if applicable)
If no listings found within budget, state the actual lowest price found and
suggest: widen price by $X, OR go back to {year} model, OR expand radius.

## Manual search links
- Facebook Marketplace Miami: https://www.facebook.com/marketplace/miami/hyundai-tucson/
- Craigslist South FL: https://miami.craigslist.org/search/cta?auto_make_model={make}+{model}
- eBay Motors: https://www.ebay.com/sch/Cars-Trucks/6001/i.html?_nkw={year}+{make}+{model}+{trim}
```

## Important rules

- **Never fabricate listings.** Only include cars that appeared in actual search results.
- If a source returns no results, skip it silently.
- Always include a direct link for every listing.
- If the budget is unrealistic for the year/model requested, say so clearly with data.
- Run all 7 WebSearch calls in parallel — do not run them one by one.
