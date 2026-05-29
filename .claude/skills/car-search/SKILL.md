---
name: car-search
description: Search the internet for used cars across multiple listing sites. Use when the user wants to find used cars by brand, model, year, price, or distance from a zip code. Returns sorted results by best value (lowest price + lowest miles).
---

# Used Car Search Skill

Search for used cars across CarGurus, Cars.com, AutoTrader, TrueCar, Craigslist, and dealer sites.

## Parameters

Parse the user's request for:
- `make` – brand/manufacturer (e.g. Toyota, Honda, Ford)
- `model` – car model (e.g. Camry, Civic, F-150)
- `year_min` / `year_max` – year range (e.g. 2018-2022)
- `zip` – ZIP code for proximity search
- `max_miles` – maximum search radius in miles from zip (default 100)
- `max_price` – maximum price in USD (optional)
- `max_odometer` – maximum odometer reading in miles (optional)

## Instructions

When this skill is invoked, run the Python script below by calling the Bash tool. Pass parameters via environment variables. After the script runs, present the results as a ranked table sorted by **Score** (best value first). Highlight the top 3 picks with a brief note on why each is a good deal.

### Step 1 – Install dependencies if needed

```bash
pip install -q requests beautifulsoup4 lxml 2>/dev/null | tail -1
```

### Step 2 – Run the search

Save the script to `/tmp/car_search.py` and run it with the user's parameters exported as env vars:

```bash
export CAR_MAKE="Toyota"
export CAR_MODEL="Camry"
export YEAR_MIN="2018"
export YEAR_MAX="2022"
export ZIP_CODE="90210"
export SEARCH_RADIUS="100"
export MAX_PRICE="20000"
export MAX_ODOMETER="80000"
python3 /tmp/car_search.py
```

### Step 3 – Present results

Show a markdown table of the top 20 results ranked by Score. Add a "Top Picks" section calling out the 3 best deals.

---

## Python Script

Write the following to `/tmp/car_search.py`:

```python
#!/usr/bin/env python3
"""
Used car search aggregator.
Searches CarGurus, Cars.com, AutoTrader, and CarMax for the best deals.
Results ranked by a value score: lower price + lower miles = higher score.
"""

import os, sys, json, time, math, re
from urllib.parse import urlencode, quote_plus
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

# ── Config from env ──────────────────────────────────────────────────────────
MAKE          = os.environ.get("CAR_MAKE", "").strip()
MODEL         = os.environ.get("CAR_MODEL", "").strip()
YEAR_MIN      = os.environ.get("YEAR_MIN", "2015").strip()
YEAR_MAX      = os.environ.get("YEAR_MAX", str(datetime.now().year)).strip()
ZIP_CODE      = os.environ.get("ZIP_CODE", "90210").strip()
RADIUS        = os.environ.get("SEARCH_RADIUS", "100").strip()
MAX_PRICE     = os.environ.get("MAX_PRICE", "").strip()
MAX_ODOMETER  = os.environ.get("MAX_ODOMETER", "").strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

results = []


# ── Helpers ──────────────────────────────────────────────────────────────────
def clean_price(s):
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


def clean_miles(s):
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


def value_score(price, miles):
    """Lower is better. Combines normalised price and miles."""
    if not price or not miles:
        return 9999999
    # weight: 60% price, 40% miles (normalise to 0-1 over typical ranges)
    p_norm = price / 100_000
    m_norm = miles / 300_000
    return round(0.6 * p_norm + 0.4 * m_norm, 6)


def fetch(url, timeout=15):
    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None


def add(source, title, price, miles, year, location, url):
    p = clean_price(price)
    m = clean_miles(miles)
    if MAX_PRICE and p and p > int(MAX_PRICE):
        return
    if MAX_ODOMETER and m and m > int(MAX_ODOMETER):
        return
    results.append({
        "source":   source,
        "title":    title[:60] if title else "N/A",
        "price":    p,
        "miles":    m,
        "year":     year,
        "location": (location or "")[:30],
        "url":      url or "",
        "score":    value_score(p, m),
    })


# ── CarGurus ─────────────────────────────────────────────────────────────────
def search_cargurus():
    print("  Searching CarGurus...", flush=True)
    params = {
        "zip":           ZIP_CODE,
        "distance":      RADIUS,
        "searchChanged": "true",
        "makeId":        "",
        "modelId":       "",
        "trim":          "",
        "yearMin":       YEAR_MIN,
        "yearMax":       YEAR_MAX,
        "mileageMax":    MAX_ODOMETER or "",
        "priceMax":      MAX_PRICE or "",
        "listingTypes":  "USED,CPO",
        "sortDir":       "ASC",
        "sortType":      "PRICE",
        "action":        "search",
        "entitySelectingHelper.selectedEntity2": f"{MAKE} {MODEL}".strip(),
    }
    url = f"https://www.cargurus.com/Cars/new/nl/Cars-d448?{urlencode({k:v for k,v in params.items() if v})}"
    # CarGurus also has a listings endpoint
    api_url = (
        f"https://www.cargurus.com/Cars/new/filterResults.action?"
        f"zip={ZIP_CODE}&distance={RADIUS}"
        f"&yearMin={YEAR_MIN}&yearMax={YEAR_MAX}"
        f"&listingTypes=USED%2CCPO&sortDir=ASC&sortType=PRICE"
        f"&trim=&action=search"
        f"&entitySelectingHelper.selectedEntity2={quote_plus(MAKE+' '+MODEL)}"
    )
    html = fetch(api_url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("[data-cg-ft='car-blade-link'], .cg-dealFinder-result-car"):
        try:
            title_el = card.select_one(".car-name, h4, [class*='title']")
            price_el = card.select_one("[class*='price'], .price")
            miles_el = card.select_one("[class*='mileage'], [class*='miles']")
            loc_el   = card.select_one("[class*='location'], [class*='dealer']")
            link_el  = card.select_one("a[href]")
            title = title_el.get_text(strip=True) if title_el else f"{YEAR_MIN}+ {MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            miles = miles_el.get_text(strip=True) if miles_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = "https://www.cargurus.com" + link_el["href"] if link_el else url
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("CarGurus", title, price, miles, year, loc, href)
        except Exception:
            pass
    print(f"    CarGurus: found {len([r for r in results if r['source']=='CarGurus'])} listings", flush=True)


# ── Cars.com ─────────────────────────────────────────────────────────────────
def search_cars_com():
    print("  Searching Cars.com...", flush=True)
    make_slug  = MAKE.lower().replace(" ", "-")
    model_slug = MODEL.lower().replace(" ", "-")
    params = {
        "stock_type":  "used",
        "makes[]":     make_slug,
        "models[]":    f"{make_slug}-{model_slug}",
        "year_min":    YEAR_MIN,
        "year_max":    YEAR_MAX,
        "zip":         ZIP_CODE,
        "maximum_distance": RADIUS,
        "sort":        "price_low",
    }
    if MAX_PRICE:
        params["price_max"] = MAX_PRICE
    if MAX_ODOMETER:
        params["mileage_max"] = MAX_ODOMETER
    url = f"https://www.cars.com/shopping/results/?{urlencode(params)}"
    html = fetch(url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("div.vehicle-card, [data-qa='vehicle-card']"):
        try:
            title_el = card.select_one(".vehicle-card-main-title, h2")
            price_el = card.select_one(".primary-price, [data-qa='primary-price']")
            miles_el = card.select_one(".mileage, [data-qa='mileage']")
            loc_el   = card.select_one(".dealer-name, [data-qa='dealer-name']")
            link_el  = card.select_one("a.vehicle-card-link, a[href*='/vehicledetail/']")
            title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            miles = miles_el.get_text(strip=True) if miles_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = "https://www.cars.com" + link_el["href"] if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else url)
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("Cars.com", title, price, miles, year, loc, href)
        except Exception:
            pass
    print(f"    Cars.com: found {len([r for r in results if r['source']=='Cars.com'])} listings", flush=True)


# ── AutoTrader ───────────────────────────────────────────────────────────────
def search_autotrader():
    print("  Searching AutoTrader...", flush=True)
    make_code  = MAKE.upper()
    model_code = MODEL.upper()
    params = {
        "makeCode":    make_code,
        "modelCode":   model_code,
        "startYear":   YEAR_MIN,
        "endYear":     YEAR_MAX,
        "zip":         ZIP_CODE,
        "searchRadius": RADIUS,
        "listingTypes": "USED,CERT_USED",
        "sortBy":      "priceASC",
        "numRecords":  "100",
        "firstRecord": "0",
    }
    if MAX_PRICE:
        params["maxPrice"] = MAX_PRICE
    if MAX_ODOMETER:
        params["maxMileage"] = MAX_ODOMETER
    url = f"https://www.autotrader.com/cars-for-sale/used-cars/{make_code}/{model_code}?{urlencode(params)}"
    html = fetch(url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("[data-cmp='itemCard'], .listing-item, [class*='inventory-listing']"):
        try:
            title_el = card.select_one("h2, h3, [class*='title']")
            price_el = card.select_one("[class*='price'], [data-cmp='firstPrice']")
            miles_el = card.select_one("[class*='mileage'], [class*='miles']")
            loc_el   = card.select_one("[class*='dealer'], [class*='location']")
            link_el  = card.select_one("a[href]")
            title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            miles = miles_el.get_text(strip=True) if miles_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = link_el["href"] if link_el else url
            if href.startswith("/"):
                href = "https://www.autotrader.com" + href
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("AutoTrader", title, price, miles, year, loc, href)
        except Exception:
            pass
    print(f"    AutoTrader: found {len([r for r in results if r['source']=='AutoTrader'])} listings", flush=True)


# ── CarMax ───────────────────────────────────────────────────────────────────
def search_carmax():
    print("  Searching CarMax...", flush=True)
    params = {
        "make":      MAKE,
        "model":     MODEL,
        "zip":       ZIP_CODE,
        "radius":    RADIUS,
        "yearMin":   YEAR_MIN,
        "yearMax":   YEAR_MAX,
        "sortBy":    "bestmatch",
    }
    url = f"https://www.carmax.com/cars/{MAKE.lower()}/{MODEL.lower()}?{urlencode(params)}"
    html = fetch(url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("[class*='car-tile'], [data-qa*='car-tile'], .kmx-car-tile"):
        try:
            title_el = card.select_one("[class*='title'], h2, h3")
            price_el = card.select_one("[class*='price']")
            miles_el = card.select_one("[class*='mileage'], [class*='miles']")
            loc_el   = card.select_one("[class*='store'], [class*='location']")
            link_el  = card.select_one("a[href]")
            title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            miles = miles_el.get_text(strip=True) if miles_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = link_el["href"] if link_el else url
            if href.startswith("/"):
                href = "https://www.carmax.com" + href
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("CarMax", title, price, miles, year, loc, href)
        except Exception:
            pass
    print(f"    CarMax: found {len([r for r in results if r['source']=='CarMax'])} listings", flush=True)


# ── TrueCar ──────────────────────────────────────────────────────────────────
def search_truecar():
    print("  Searching TrueCar...", flush=True)
    make_slug  = MAKE.lower()
    model_slug = MODEL.lower()
    params = {
        "zip_code":    ZIP_CODE,
        "search_radius": RADIUS,
        "year[]":      [str(y) for y in range(int(YEAR_MIN), int(YEAR_MAX)+1)],
        "sort[]":      "price:asc",
    }
    url = f"https://www.truecar.com/used-cars-for-sale/listings/{make_slug}/{model_slug}/?{urlencode(params, doseq=True)}"
    html = fetch(url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("[data-test='cardContent'], [class*='vehicle-card']"):
        try:
            title_el = card.select_one("[data-test='vehicleCardTitle'], h2")
            price_el = card.select_one("[data-test='vehicleCardPricingBlockPrice'], [class*='price']")
            miles_el = card.select_one("[data-test='vehicleMileage'], [class*='mileage']")
            loc_el   = card.select_one("[data-test='dealerName'], [class*='dealer']")
            link_el  = card.select_one("a[href]")
            title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            miles = miles_el.get_text(strip=True) if miles_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = link_el["href"] if link_el else url
            if href.startswith("/"):
                href = "https://www.truecar.com" + href
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("TrueCar", title, price, miles, year, loc, href)
        except Exception:
            pass
    print(f"    TrueCar: found {len([r for r in results if r['source']=='TrueCar'])} listings", flush=True)


# ── Craigslist ───────────────────────────────────────────────────────────────
def search_craigslist():
    """Search craigslist using the national search aggregator."""
    print("  Searching Craigslist...", flush=True)
    query = f"{MAKE} {MODEL}".strip()
    params = {
        "auto_make_model": query,
        "min_auto_year":   YEAR_MIN,
        "max_auto_year":   YEAR_MAX,
        "postal":          ZIP_CODE,
        "search_distance": RADIUS,
        "sort":            "priceasc",
        "auto_title_status": "1",  # clean title only
    }
    if MAX_PRICE:
        params["max_price"] = MAX_PRICE
    if MAX_ODOMETER:
        params["max_auto_miles"] = MAX_ODOMETER
    url = f"https://www.craigslist.org/search/cta?{urlencode(params)}"
    html = fetch(url)
    if not html:
        return
    soup = BeautifulSoup(html, "lxml")
    for item in soup.select(".result-row, li.cl-search-result"):
        try:
            title_el = card.select_one(".result-title, [class*='title']") if False else item.select_one(".result-title, a.titlestring")
            price_el = item.select_one(".result-price")
            loc_el   = item.select_one(".result-hood, .nearby")
            link_el  = item.select_one("a[href]")
            title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
            price = price_el.get_text(strip=True) if price_el else None
            loc   = loc_el.get_text(strip=True) if loc_el else ""
            href  = link_el["href"] if link_el else url
            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN
            add("Craigslist", title, price, None, year, loc, href)
        except Exception:
            pass
    print(f"    Craigslist: found {len([r for r in results if r['source']=='Craigslist'])} listings", flush=True)


# ── Facebook Marketplace hint ────────────────────────────────────────────────
def add_facebook_link():
    q = quote_plus(f"{MAKE} {MODEL}")
    results.append({
        "source":   "Facebook Marketplace",
        "title":    f"Search {MAKE} {MODEL} on Facebook Marketplace",
        "price":    None,
        "miles":    None,
        "year":     YEAR_MIN,
        "location": ZIP_CODE,
        "url":      f"https://www.facebook.com/marketplace/search/?query={q}&daysSinceListed=30&sortBy=price_ascend",
        "score":    9999998,
    })


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not MAKE or not MODEL:
        print("ERROR: CAR_MAKE and CAR_MODEL environment variables are required.")
        sys.exit(1)

    print(f"\nSearching for: {MAKE} {MODEL} ({YEAR_MIN}-{YEAR_MAX})")
    print(f"Location: {ZIP_CODE}, radius: {RADIUS} miles")
    if MAX_PRICE:     print(f"Max price: ${int(MAX_PRICE):,}")
    if MAX_ODOMETER:  print(f"Max odometer: {int(MAX_ODOMETER):,} miles")
    print("-" * 60)

    for fn in [search_cargurus, search_cars_com, search_autotrader, search_carmax, search_truecar, search_craigslist]:
        try:
            fn()
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error in {fn.__name__}: {e}", flush=True)

    add_facebook_link()

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for r in results:
        key = r["url"][:80]
        if key not in seen_urls:
            seen_urls.add(key)
            deduped.append(r)

    # Sort: listings with actual price+miles first, then by score
    ranked = sorted(deduped, key=lambda r: (r["score"] == 9999999, r["score"]))

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(ranked)} listings found (sorted by best value)")
    print(f"{'='*60}")

    if not ranked or all(r["score"] >= 9999998 for r in ranked):
        print("\nNo priced listings found. Try broadening your search parameters.")
        print("Direct search links:")
        for site, url in [
            ("CarGurus",    f"https://www.cargurus.com/Cars/new/nl/Cars-d448?zip={ZIP_CODE}&distance={RADIUS}&yearMin={YEAR_MIN}&yearMax={YEAR_MAX}&listingTypes=USED"),
            ("Cars.com",    f"https://www.cars.com/shopping/results/?stock_type=used&makes[]={MAKE.lower()}&zip={ZIP_CODE}&maximum_distance={RADIUS}&year_min={YEAR_MIN}&year_max={YEAR_MAX}&sort=price_low"),
            ("AutoTrader",  f"https://www.autotrader.com/cars-for-sale/used-cars/{MAKE.upper()}/{MODEL.upper()}?zip={ZIP_CODE}&searchRadius={RADIUS}&startYear={YEAR_MIN}&endYear={YEAR_MAX}&sortBy=priceASC"),
            ("TrueCar",     f"https://www.truecar.com/used-cars-for-sale/listings/{MAKE.lower()}/{MODEL.lower()}/?zip_code={ZIP_CODE}"),
            ("CarMax",      f"https://www.carmax.com/cars/{MAKE.lower()}/{MODEL.lower()}"),
            ("Facebook MP", f"https://www.facebook.com/marketplace/search/?query={quote_plus(MAKE+' '+MODEL)}&sortBy=price_ascend"),
        ]:
            print(f"  {site}: {url}")
        return

    # Print table
    print(f"\n{'#':<4} {'Source':<15} {'Title':<45} {'Year':<6} {'Price':>10} {'Miles':>10} {'Location':<25}")
    print("-" * 120)
    for i, r in enumerate(ranked[:30], 1):
        price_str = f"${r['price']:,}"  if r['price'] else "N/A"
        miles_str = f"{r['miles']:,} mi" if r['miles'] else "N/A"
        print(f"{i:<4} {r['source']:<15} {r['title']:<45} {r['year']:<6} {price_str:>10} {miles_str:>10} {r['location']:<25}")

    print("\n" + "="*60)
    print("TOP PICKS (best value = low price + low miles)")
    print("="*60)
    top = [r for r in ranked if r["score"] < 9999998][:3]
    for i, r in enumerate(top, 1):
        price_str = f"${r['price']:,}" if r['price'] else "N/A"
        miles_str = f"{r['miles']:,} miles" if r['miles'] else "N/A"
        print(f"\n#{i}: {r['title']}")
        print(f"    Price: {price_str}  |  Odometer: {miles_str}  |  Source: {r['source']}")
        print(f"    Location: {r['location']}")
        print(f"    Link: {r['url']}")

    print("\n" + "-"*60)
    print("Direct search links for manual browsing:")
    print(f"  CarGurus:    https://www.cargurus.com/Cars/new/nl/Cars-d448?zip={ZIP_CODE}&distance={RADIUS}&yearMin={YEAR_MIN}&yearMax={YEAR_MAX}&listingTypes=USED")
    print(f"  Cars.com:    https://www.cars.com/shopping/results/?stock_type=used&makes[]={MAKE.lower()}&zip={ZIP_CODE}&maximum_distance={RADIUS}&year_min={YEAR_MIN}&year_max={YEAR_MAX}&sort=price_low")
    print(f"  AutoTrader:  https://www.autotrader.com/cars-for-sale/used-cars/{MAKE.upper()}/{MODEL.upper()}?zip={ZIP_CODE}&searchRadius={RADIUS}&startYear={YEAR_MIN}&endYear={YEAR_MAX}&sortBy=priceASC")
    print(f"  TrueCar:     https://www.truecar.com/used-cars-for-sale/listings/{MAKE.lower()}/{MODEL.lower()}/?zip_code={ZIP_CODE}")
    print(f"  CarMax:      https://www.carmax.com/cars/{MAKE.lower()}/{MODEL.lower()}")
    print(f"  Facebook MP: https://www.facebook.com/marketplace/search/?query={quote_plus(MAKE+' '+MODEL)}&sortBy=price_ascend")
    print(f"  Craigslist:  https://www.craigslist.org/search/cta?auto_make_model={quote_plus(MAKE+' '+MODEL)}&postal={ZIP_CODE}&search_distance={RADIUS}&sort=priceasc")


if __name__ == "__main__":
    main()
```

---

## How Claude should invoke this skill

1. Parse the user's request to extract make, model, year range, zip, radius, max price, max odometer.
2. If zip is missing, ask the user for it — it is required.
3. Set defaults: year range = last 7 years, radius = 100 miles.
4. Write the Python script to `/tmp/car_search.py`.
5. Run the script with env vars set.
6. Parse stdout and present the ranked table plus top picks in a clean markdown response.
7. Always include the direct search links at the bottom so the user can manually browse too.
