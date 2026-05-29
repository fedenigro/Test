---
name: car-search
description: Search the internet for used cars across non-traditional listing sites (Craigslist, eBay Motors, OfferUp, Facebook Marketplace, local dealer sites). Use when the user wants to find used cars by brand, model, year, price, or distance from a zip code. Finds deals that don't appear on Cars.com or AutoTrader.
---

# Used Car Search Skill

Searches non-traditional sources for used car listings: Craigslist (all nearby cities),
eBay Motors (auctions + buy-it-now), OfferUp, and individual dealer websites.
Runs as a Python script — requires local Claude Code CLI with real internet access.

## Step 1 — Parse parameters

Extract from the user's request:
- `make` – e.g. Hyundai, Toyota, Ford
- `model` – e.g. Tucson, Camry, F-150
- `year_min` / `year_max` – default to last 5 years if not specified
- `zip` – required; ask the user if missing
- `radius` – miles from zip, default 100
- `max_price` – optional price ceiling in USD
- `max_odometer` – optional odometer ceiling in miles
- `trim` – optional trim filter (e.g. SEL, EX, Limited); "SEL or higher" = SEL,Limited,N-Line,Calligraphy,Ultimate

## Step 2 — Write and run the script

Write the full Python script below to `/tmp/car_search.py`, then run it:

```bash
export CAR_MAKE="Hyundai"
export CAR_MODEL="Tucson"
export YEAR_MIN="2022"
export YEAR_MAX="2025"
export ZIP_CODE="33160"
export SEARCH_RADIUS="100"
export MAX_PRICE="21000"
export MAX_ODOMETER=""
export TRIM_FILTER="SEL,LIMITED,N-LINE,CALLIGRAPHY,ULTIMATE"
python3 /tmp/car_search.py
```

Fill in values from the user's request. Omit MAX_PRICE or MAX_ODOMETER if not specified (leave as empty string).

## Step 3 — Present results

After the script runs, format the output as:
- A ranked markdown table (best value first)
- A **Top 3 Picks** section with direct links and a one-line reason why each is a good deal
- Note which sources returned results and which were unreachable

---

## Python Script

```python
#!/usr/bin/env python3
"""
Used car search — non-traditional sources.
Searches Craigslist (multi-city), eBay Motors, OfferUp, and local dealer
Google results. Results ranked by value score (price + miles).
"""

import os, sys, re, time, json, urllib.parse
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                           "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────
MAKE         = os.environ.get("CAR_MAKE", "").strip()
MODEL        = os.environ.get("CAR_MODEL", "").strip()
YEAR_MIN     = os.environ.get("YEAR_MIN", str(datetime.now().year - 5)).strip()
YEAR_MAX     = os.environ.get("YEAR_MAX", str(datetime.now().year)).strip()
ZIP_CODE     = os.environ.get("ZIP_CODE", "").strip()
RADIUS       = int(os.environ.get("SEARCH_RADIUS", "100").strip())
MAX_PRICE    = os.environ.get("MAX_PRICE", "").strip()
MAX_ODOMETER = os.environ.get("MAX_ODOMETER", "").strip()
TRIM_FILTER  = [t.strip().upper() for t in os.environ.get("TRIM_FILTER", "").split(",") if t.strip()]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

S = requests.Session()
S.headers.update(HEADERS)

results = []

# Craigslist cities within ~100-150 miles of common metro zips
# Keyed by state prefix of zip; expands automatically for nearby cities
CRAIGSLIST_METROS = {
    # Florida
    "331": ["miami", "broward", "palmbeach", "keys", "swflorida"],
    "332": ["miami", "broward"],
    "333": ["miami", "broward", "palmbeach"],
    "334": ["tampa", "sarasota", "swflorida"],
    "336": ["tampa", "orlando", "lakeland"],
    "337": ["tampa", "orlando"],
    "338": ["orlando", "daytona", "spacecoast"],
    # New York
    "100": ["newyork", "longisland", "newjersey", "connecticut", "hudson"],
    "110": ["longisland", "newyork", "newjersey"],
    # California
    "900": ["losangeles", "orangecounty", "inlandempire", "ventura"],
    "902": ["losangeles", "longbeach", "orangecounty"],
    "941": ["sfbay", "eastbay", "peninsula", "southbay", "santacruz"],
    # Texas
    "770": ["houston", "galveston", "beaumont"],
    "787": ["austin", "sanantonio", "waco"],
    # Default fallback — use a broad national search
    "default": ["miami", "losangeles", "chicago", "newyork", "dallas",
                 "houston", "atlanta", "seattle", "denver", "phoenix"],
}

def get_craigslist_cities():
    prefix = ZIP_CODE[:3] if ZIP_CODE else ""
    cities = CRAIGSLIST_METROS.get(prefix)
    if not cities:
        # Try 2-char prefix
        cities = CRAIGSLIST_METROS.get(ZIP_CODE[:2])
    if not cities:
        cities = CRAIGSLIST_METROS["default"]
    return cities


# ── Helpers ──────────────────────────────────────────────────────────────────
def clean_price(s):
    if not s: return None
    d = re.sub(r"[^\d]", "", str(s))
    return int(d) if d else None

def clean_miles(s):
    if not s: return None
    d = re.sub(r"[^\d]", "", str(s))
    return int(d) if d else None

def value_score(price, miles):
    if not price: return 9_000_000
    if not miles: return 8_000_000 + price / 100
    return round(0.6 * price / 100_000 + 0.4 * miles / 300_000, 6)

def trim_ok(title):
    if not TRIM_FILTER: return True
    t = title.upper()
    return any(tr in t for tr in TRIM_FILTER)

def price_ok(p):
    if not MAX_PRICE or not p: return True
    return p <= int(MAX_PRICE)

def miles_ok(m):
    if not MAX_ODOMETER or not m: return True
    return m <= int(MAX_ODOMETER)

def add(source, title, price, miles, year, seller, location, url):
    p, m = clean_price(price), clean_miles(miles)
    if not price_ok(p) or not miles_ok(m): return
    if not trim_ok(title or ""): return
    results.append({
        "source":   source,
        "title":    (title or "N/A")[:70],
        "price":    p,
        "miles":    m,
        "year":     str(year or ""),
        "seller":   (seller or "")[:35],
        "location": (location or "")[:30],
        "url":      url or "",
        "score":    value_score(p, m),
    })

def fetch(url, timeout=12):
    try:
        r = S.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


# ── Craigslist (multi-city) ──────────────────────────────────────────────────
def search_craigslist():
    cities = get_craigslist_cities()
    query = urllib.parse.quote_plus(f"{MAKE} {MODEL}")
    total = 0
    print(f"  Searching Craigslist ({len(cities)} cities)...", flush=True)

    for city in cities:
        params = {
            "auto_make_model": f"{MAKE} {MODEL}",
            "min_auto_year":   YEAR_MIN,
            "max_auto_year":   YEAR_MAX,
            "sort":            "priceasc",
            "auto_title_status": "1",  # clean title only
        }
        if MAX_PRICE:    params["max_price"] = MAX_PRICE
        if MAX_ODOMETER: params["max_auto_miles"] = MAX_ODOMETER

        url = f"https://{city}.craigslist.org/search/cta?{urllib.parse.urlencode(params)}"
        html = fetch(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        city_count = 0

        # New Craigslist layout
        for item in soup.select("li.cl-search-result, .result-row"):
            try:
                title_el = item.select_one("a.cl-app-anchor, .result-title, a.titlestring")
                price_el = item.select_one(".priceinfo, .result-price")
                meta_el  = item.select_one(".meta, .result-meta")
                link_el  = item.select_one("a[href]")

                title = title_el.get_text(strip=True) if title_el else f"{MAKE} {MODEL}"
                price = price_el.get_text(strip=True) if price_el else None
                meta  = meta_el.get_text(" ", strip=True) if meta_el else ""
                href  = link_el["href"] if link_el else url

                # Extract miles from meta text
                miles_m = re.search(r"([\d,]+)\s*mi", meta, re.I)
                miles = miles_m.group(1) if miles_m else None

                year_m = re.search(r"(20\d\d|19\d\d)", title)
                year = year_m.group(1) if year_m else YEAR_MIN

                loc = city.replace("sfbay", "SF Bay").title()
                before = len(results)
                add("Craigslist", title, price, miles, year, "Private/Dealer", loc, href)
                if len(results) > before:
                    city_count += 1
            except Exception:
                pass

        total += city_count
        if city_count > 0:
            print(f"    {city}: {city_count} listings", flush=True)
        time.sleep(0.3)

    print(f"  Craigslist total: {total} listings", flush=True)


# ── eBay Motors ──────────────────────────────────────────────────────────────
def search_ebay_motors():
    print("  Searching eBay Motors...", flush=True)

    params = {
        "_nkw":          f"{YEAR_MIN}-{YEAR_MAX} {MAKE} {MODEL}",
        "_sacat":        "6001",       # Cars & Trucks
        "LH_ItemCondition": "3000",    # Used
        "_sop":          "15",         # Sort by price + shipping: lowest first
        "LH_PrefLoc":    "99",         # US only
    }
    if MAX_PRICE:
        params["_udhi"] = MAX_PRICE
    if ZIP_CODE:
        params["_stpos"] = ZIP_CODE
        params["_sadis"] = str(RADIUS)

    url = f"https://www.ebay.com/sch/Cars-Trucks/6001/i.html?{urllib.parse.urlencode(params)}"
    html = fetch(url)
    if not html:
        print("  eBay Motors: no response", flush=True)
        return

    soup = BeautifulSoup(html, "lxml")
    count = 0

    for item in soup.select(".s-item, [data-view='mi:1686|iid:1']"):
        try:
            title_el    = item.select_one(".s-item__title, h3.s-item__title")
            price_el    = item.select_one(".s-item__price, .notranslate")
            miles_el    = item.select_one(".s-item__subtitle, .s-item__detail")
            loc_el      = item.select_one(".s-item__location, .s-item__itemLocation")
            link_el     = item.select_one("a.s-item__link, a[href*='ebay.com/itm']")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title or "Shop on eBay" in title: continue

            price  = price_el.get_text(strip=True) if price_el else None
            detail = miles_el.get_text(" ", strip=True) if miles_el else ""
            loc    = loc_el.get_text(strip=True).replace("From ", "") if loc_el else ""
            href   = link_el["href"] if link_el else url

            miles_m = re.search(r"([\d,]+)\s*mi", detail, re.I)
            miles = miles_m.group(1) if miles_m else None

            year_m = re.search(r"(20\d\d|19\d\d)", title)
            year = year_m.group(1) if year_m else YEAR_MIN

            before = len(results)
            add("eBay Motors", title, price, miles, year, "eBay Seller", loc, href)
            if len(results) > before:
                count += 1
        except Exception:
            pass

    print(f"  eBay Motors: {count} listings", flush=True)


# ── OfferUp ──────────────────────────────────────────────────────────────────
def search_offerup():
    print("  Searching OfferUp...", flush=True)

    params = {
        "q":              f"{MAKE} {MODEL}",
        "distance":       str(RADIUS),
        "zip":            ZIP_CODE,
        "delivery_param": "ls",
        "FSBO":           "1",
    }
    if MAX_PRICE: params["price_max"] = MAX_PRICE

    url = f"https://offerup.com/search/?{urllib.parse.urlencode(params)}"
    html = fetch(url)
    if not html:
        print("  OfferUp: no response", flush=True)
        return

    soup = BeautifulSoup(html, "lxml")
    count = 0

    # OfferUp embeds listing data in a __NEXT_DATA__ JSON script
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        try:
            data = json.loads(next_data.string)
            items = (data.get("props", {})
                        .get("pageProps", {})
                        .get("listingSearchResult", {})
                        .get("data", {})
                        .get("search", {})
                        .get("customFeed", {})
                        .get("tiles", []))
            for tile in items:
                listing = tile.get("listing", {})
                title  = listing.get("title", "")
                price  = listing.get("price", {}).get("amount")
                loc    = listing.get("location", {}).get("city", "")
                lid    = listing.get("id", "")
                href   = f"https://offerup.com/item/detail/{lid}/" if lid else url

                year_m = re.search(r"(20\d\d|19\d\d)", title)
                year = year_m.group(1) if year_m else YEAR_MIN

                before = len(results)
                add("OfferUp", title, price, None, year, "Private Seller", loc, href)
                if len(results) > before:
                    count += 1
        except Exception:
            pass

    if count == 0:
        # Fallback: plain HTML parse
        for card in soup.select("[data-testid='listing-card'], .listing-card"):
            try:
                title_el = card.select_one("p, h3, [class*='title']")
                price_el = card.select_one("[class*='price']")
                link_el  = card.select_one("a[href]")
                title = title_el.get_text(strip=True) if title_el else ""
                price = price_el.get_text(strip=True) if price_el else None
                href  = "https://offerup.com" + link_el["href"] if link_el else url
                year_m = re.search(r"(20\d\d|19\d\d)", title)
                year = year_m.group(1) if year_m else YEAR_MIN
                before = len(results)
                add("OfferUp", title, price, None, year, "Private Seller", "", href)
                if len(results) > before: count += 1
            except Exception:
                pass

    print(f"  OfferUp: {count} listings", flush=True)


# ── Facebook Marketplace (public JSON endpoint) ──────────────────────────────
def search_facebook():
    """
    Facebook requires auth for full results. We attempt the public
    marketplace search which sometimes returns listings for logged-out users.
    """
    print("  Searching Facebook Marketplace...", flush=True)
    params = {
        "query":          f"{MAKE} {MODEL}",
        "latitude":       "",   # Would need geocoding; skip for now
        "longitude":      "",
        "radius":         str(RADIUS * 1609),  # metres
        "price_upper":    MAX_PRICE or "",
        "daysSinceListed": "30",
        "sortBy":         "price_ascend",
    }
    url = f"https://www.facebook.com/marketplace/search/?{urllib.parse.urlencode({k:v for k,v in params.items() if v})}"
    html = fetch(url)
    count = 0

    if html:
        soup = BeautifulSoup(html, "lxml")
        # FB embeds listings in JSON inside script tags
        for script in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(script.string or "")
                text = json.dumps(data)
                # Look for price + title patterns
                titles  = re.findall(r'"name"\s*:\s*"([^"]{5,60})"', text)
                prices  = re.findall(r'"amount"\s*:\s*"(\d+)"', text)
                for i, title in enumerate(titles[:20]):
                    if MAKE.lower() in title.lower() or MODEL.lower() in title.lower():
                        price = prices[i] if i < len(prices) else None
                        year_m = re.search(r"(20\d\d|19\d\d)", title)
                        year = year_m.group(1) if year_m else YEAR_MIN
                        before = len(results)
                        add("Facebook MP", title, price, None, year, "Private Seller", "", url)
                        if len(results) > before: count += 1
            except Exception:
                pass

    if count == 0:
        print("  Facebook Marketplace: requires login — adding manual link", flush=True)
        q = urllib.parse.quote_plus(f"{MAKE} {MODEL}")
        results.append({
            "source": "Facebook MP", "title": f"Search {MAKE} {MODEL} — click to open",
            "price": None, "miles": None, "year": YEAR_MIN,
            "seller": "Manual search", "location": f"Near {ZIP_CODE}",
            "url": f"https://www.facebook.com/marketplace/search/?query={q}&sortBy=price_ascend",
            "score": 9_999_999,
        })
    else:
        print(f"  Facebook Marketplace: {count} listings", flush=True)


# ── Google — individual dealer inventory pages ───────────────────────────────
def search_dealer_sites():
    """
    Use Google to surface individual dealer inventory pages that never
    appear on aggregator sites. Targets common dealer CMS platforms.
    """
    print("  Searching dealer sites via Google...", flush=True)

    year_range = f"{YEAR_MIN}" if YEAR_MIN == YEAR_MAX else f"{YEAR_MIN}..{YEAR_MAX}"
    price_part = f"under ${int(MAX_PRICE):,}" if MAX_PRICE else ""
    trim_part  = TRIM_FILTER[0] if TRIM_FILTER else ""

    query = (
        f"{year_range} {MAKE} {MODEL} {trim_part} used {price_part} "
        f"near {ZIP_CODE} "
        f"(site:dealer.com OR site:dealerfire.com OR site:dealerinspire.com "
        f"OR site:vin.li OR site:cdk.com OR inurl:inventory OR inurl:used-cars)"
    )

    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&num=20"
    html = fetch(url)
    if not html:
        print("  Dealer sites (Google): no response", flush=True)
        return

    soup = BeautifulSoup(html, "lxml")
    count = 0

    for result in soup.select(".g, div[data-sokoban-container]"):
        try:
            title_el = result.select_one("h3")
            link_el  = result.select_one("a[href]")
            desc_el  = result.select_one(".VwiC3b, span.st")

            title = title_el.get_text(strip=True) if title_el else ""
            desc  = desc_el.get_text(strip=True) if desc_el else ""
            href  = link_el["href"] if link_el else ""

            if not title or not href or href.startswith("/search"): continue
            if not any(kw in title.lower() or kw in desc.lower()
                       for kw in [MAKE.lower(), MODEL.lower()]): continue

            # Extract price from snippet
            price_m = re.search(r"\$\s*([\d,]+)", desc)
            price = price_m.group(1) if price_m else None

            miles_m = re.search(r"([\d,]+)\s*(?:miles?|mi\.?)", desc, re.I)
            miles = miles_m.group(1) if miles_m else None

            year_m = re.search(r"(20\d\d|19\d\d)", title + " " + desc)
            year = year_m.group(1) if year_m else YEAR_MIN

            # Get domain as seller name
            domain_m = re.search(r"https?://(?:www\.)?([^/]+)", href)
            seller = domain_m.group(1) if domain_m else "Dealer"

            before = len(results)
            add("Dealer Site", title, price, miles, year, seller, "", href)
            if len(results) > before: count += 1
        except Exception:
            pass

    print(f"  Dealer sites (Google): {count} listings", flush=True)


# ── Deduplicate & rank ────────────────────────────────────────────────────────
def rank(raw):
    seen, out = set(), []
    for r in raw:
        key = f"{r['title'][:30]}|{r['price']}|{r['miles']}"
        if key not in seen:
            seen.add(key)
            out.append(r)
    return sorted(out, key=lambda r: (r["score"] >= 9_000_000, r["score"]))


# ── Output ────────────────────────────────────────────────────────────────────
def print_results(ranked):
    print(f"\n{'='*70}")
    print(f"RESULTS: {len(ranked)} listings  |  sorted by best value (price + miles)")
    print(f"{'='*70}")

    priced = [r for r in ranked if r["score"] < 9_000_000]
    unpriced = [r for r in ranked if r["score"] >= 9_000_000]

    if not priced:
        print("\nNo priced listings found. Try broadening year range, radius, or price.")
    else:
        print(f"\n{'#':<4} {'Source':<14} {'Title':<52} {'Yr':<5} {'Price':>9} {'Miles':>9}  Location")
        print("-" * 105)
        for i, r in enumerate(priced[:30], 1):
            ps = f"${r['price']:,}" if r['price'] else "N/A"
            ms = f"{r['miles']:,}mi" if r['miles'] else "N/A"
            print(f"{i:<4} {r['source']:<14} {r['title']:<52} {r['year']:<5} {ps:>9} {ms:>9}  {r['location']}")

        print(f"\n{'='*70}")
        print("TOP 3 PICKS  (lowest combined price + mileage score)")
        print(f"{'='*70}")
        for i, r in enumerate(priced[:3], 1):
            ps = f"${r['price']:,}" if r['price'] else "N/A"
            ms = f"{r['miles']:,} miles" if r['miles'] else "unknown miles"
            print(f"\n#{i}: {r['title']}")
            print(f"    {ps}  ·  {ms}  ·  {r['source']}  ·  {r['seller']}")
            print(f"    {r['location']}")
            print(f"    {r['url']}")

    if unpriced:
        print(f"\n── Manual search links ──")
        for r in unpriced:
            print(f"  {r['source']}: {r['url']}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not MAKE or not MODEL:
        print("ERROR: set CAR_MAKE and CAR_MODEL environment variables.")
        sys.exit(1)
    if not ZIP_CODE:
        print("ERROR: set ZIP_CODE environment variable.")
        sys.exit(1)

    trim_display = ", ".join(TRIM_FILTER) if TRIM_FILTER else "any"
    print(f"\n{'='*70}")
    print(f"Searching: {MAKE} {MODEL}  |  {YEAR_MIN}–{YEAR_MAX}  |  trim: {trim_display}")
    print(f"ZIP: {ZIP_CODE}  |  radius: {RADIUS}mi  |  "
          f"max price: {'$'+MAX_PRICE if MAX_PRICE else 'any'}  |  "
          f"max miles: {MAX_ODOMETER or 'any'}")
    print(f"Sources: Craigslist (multi-city), eBay Motors, OfferUp, Facebook MP, Dealer sites")
    print(f"{'='*70}\n")

    for fn in [search_craigslist, search_ebay_motors, search_offerup,
               search_facebook, search_dealer_sites]:
        try:
            fn()
        except Exception as e:
            print(f"  Error in {fn.__name__}: {e}")
        time.sleep(0.3)

    print_results(rank(results))


if __name__ == "__main__":
    main()
```
