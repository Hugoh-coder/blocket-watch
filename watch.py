# /// script
# requires-python = ">=3.10"
# dependencies = ["blocket-api"]
# ///
"""On-demand watch: road bikes (Trek/Specialized/Canyon/Bianchi), 10-25k SEK.
Sources: Blocket, Happyride, Sportson begagnat.

Usage:
  uv run watch.py            # profile std (L/XL/58, no 56), prints only NEW ads
  uv run watch.py xl61       # profile xl61 (XL/60-62), prints only NEW ads
  uv run watch.py --json     # profile std, print ALL matches as JSON (for the website)
  uv run watch.py xl61 --json

Size lives in free text (except Happyride's native bucket), so it's parsed with regex.
Profiles:
  std  = keep L / XL / 57 / 58; reject any listing stating 56 cm explicitly.
  xl61 = keep XL / 60 / 61 / 62 (the taller-rider page).
State for "new only" mode: seen_ids.json (per profile) next to this file."""
import html as html_mod
import json
import os
import pathlib
import re
import sys
import urllib.request

from blocket_api import BlocketAPI
from blocket_api.ad_parser import RecommerceAd
from blocket_api.constants import SubCategory

BRANDS = ["Trek", "Specialized", "Canyon", "Bianchi"]
BUDGETS = {"std": (10_000, 30_000), "xl61": (10_000, 25_000)}  # SEK, per profile
PAGES = 5
NOT_ROAD = re.compile(r"mountainbike|mtb|heldämpad|enduro|downhill|elcykel|e-?bike|e-?road|hybrid|bmx|lådcykel|barncykel|gravel|cyclocross|cross|triathlon|tt-cykel|city|fatbike", re.I)
MODELS = (r"domane|madone|emonda|émonda|"           # Trek
          r"tarmac|allez|roubaix|aethos|venge|"     # Specialized
          r"aeroad|ultimate|endurace|"              # Canyon
          r"oltre|sprint|specialissima|via nirone|infinito|aria|impulso|vertigo")  # Bianchi
ROAD = re.compile(r"landsväg|racer|road|aero\b|" + MODELS, re.I)
BRAND_OR_MODEL = re.compile("|".join(BRANDS) + "|" + MODELS, re.I)
MODEL_BRAND = [("Trek", "domane|madone|emonda|émonda"),
               ("Specialized", "tarmac|allez|roubaix|aethos|venge"),
               ("Canyon", "aeroad|ultimate|endurace"),
               ("Bianchi", "oltre|specialissima|via nirone|infinito|aria|impulso|vertigo")]


def size_tokens(text):
    """Return (cms:set[int], letters:set[str]) of frame sizes found in text."""
    t = text.lower()
    cms = set()
    for m in re.finditer(r"(?:strl|storlek|stl|ram(?:storlek)?|size|frame)\s*[:.\-]?\s*(\d{2})\b", t):
        cms.add(int(m.group(1)))
    for m in re.finditer(r"\b(\d{2})\s*cm\b", t):
        cms.add(int(m.group(1)))
    letters = set(re.findall(r"\b(xxl|xl|large|medium|small|xs|s|m|l)\b", t))
    norm = {"large": "l", "medium": "m", "small": "s"}
    letters = {norm.get(x, x) for x in letters}
    return {c for c in cms if 44 <= c <= 66}, letters


def size_ok(text, profile):
    cms, letters = size_tokens(text)
    if profile == "xl61":
        return bool(letters & {"xl", "xxl"} or cms & {60, 61, 62, 63})
    # std: L/XL/57/58, but an explicit 56 (or smaller relevant cm) disqualifies
    if cms & {54, 55, 56}:
        return False
    return bool(cms & {57, 58} or letters & {"l", "xl", "xxl"})


def size_label(text):
    cms, letters = size_tokens(text)
    rel = sorted(c for c in cms if 54 <= c <= 63)
    if rel:
        return f"{rel[0]} cm"
    if letters & {"xl", "xxl"}:
        return "XL"
    if "l" in letters:
        return "L"
    return ""


def brand_of(title):
    tl = title.lower()
    for b in BRANDS:
        if b.lower() in tl:
            return b
    for b, pat in MODEL_BRAND:
        if re.search(pat, tl):
            return b
    return "?"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")


def blocket(profile):
    api = BlocketAPI()
    for brand in BRANDS:
        for page in range(1, PAGES + 1):
            docs = api.search(brand, page=page, sub_category=SubCategory.CYKEL).get("docs", [])
            if not docs:
                break
            for d in docs:
                h = d["heading"]
                if brand.lower() not in h.lower() or NOT_ROAD.search(h) or not ROAD.search(h):
                    continue
                price = d.get("price") or {}
                amount = price.get("amount") if isinstance(price, dict) else price
                if not amount or not (BUDGET[0] <= amount <= BUDGET[1]):
                    continue
                sizetext = h
                if not size_tokens(h)[0] and not size_tokens(h)[1]:
                    # no size in heading — pull the ad body to classify
                    sizetext = h + " " + json.dumps(BlocketAPI().get_ad(RecommerceAd(id=int(d["id"]))), ensure_ascii=False)
                if not size_ok(sizetext, profile):
                    continue
                loc = d.get("location")
                loc = loc.get("name") if isinstance(loc, dict) else loc
                url = d.get("canonical_url") or f"https://www.blocket.se/recommerce/forsale/item/{d['id']}"
                if url.startswith("/"):
                    url = "https://www.blocket.se" + url
                yield {"id": str(d["id"]), "brand": brand_of(h), "title": h, "price": amount,
                       "loc": loc, "src": "Blocket", "url": url, "size": size_label(sizetext)}


def happyride(profile):
    bucket = "xl" if profile == "xl61" else "l"  # l = 56-58 cm, xl = 59-62 cm
    page = fetch(f"https://happyride.se/annonser/list.php?category=11&type=1"
                 f"&price_from={BUDGET[0]}&price_to={BUDGET[1]}&size_cm={bucket}")
    for path, inner in re.findall(r'<a[^>]+href="(/annonser/[a-z0-9-]+\.(?:\d+)/)"[^>]*>(.*?)</a>', page, re.S):
        text = html_mod.unescape(re.sub(r"<[^>]+>", " ", inner))
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines or not BRAND_OR_MODEL.search(lines[0]) or NOT_ROAD.search(lines[0]):
            continue
        title = lines[0]
        sizetext = title + (" XL" if bucket == "xl" else " L")
        if not size_ok(sizetext, profile):
            continue
        m = re.search(r"(?<!\d)(\d{1,3}(?:\xa0\d{3})+|\d{3,6}):-", text)
        amount = int(re.sub(r"\D", "", m.group(1))) if m else None
        if not amount or not (BUDGET[0] <= amount <= BUDGET[1]):
            continue
        not_loc = re.compile(r"^\d+\s*(min|tim|dag|veck|månad)|:-")
        locs = [l for l in lines[1:] if not not_loc.search(l)]
        loc = locs[-1] if locs else ""
        ad_id = re.search(r"\.(\d+)/$", path).group(1)
        yield {"id": f"hr-{ad_id}", "brand": brand_of(title), "title": title, "price": amount,
               "loc": loc, "src": "Happyride", "url": "https://happyride.se" + path,
               "size": size_label(sizetext)}


def sportson(profile):
    page = fetch("https://www.sportson.se/cyklar/begagnat/racer")
    for slug, name in dict(re.findall(r'href="(/produkt/[^"]+)"[^>]*>.*?alt="(Begagnad[^"]+)"', page, re.S)).items():
        name = html_mod.unescape(name)
        if not BRAND_OR_MODEL.search(name) or not size_ok(name, profile):
            continue
        card = page[max(0, page.find(slug) - 200): page.find(slug) + 3000]
        m = re.search(r"(\d{2})[\s ]?(\d{3})\s*kr", card)
        amount = int(m.group(1) + m.group(2)) if m else None
        if not amount or not (BUDGET[0] <= amount <= BUDGET[1]):
            continue
        yield {"id": f"sp-{slug}", "brand": brand_of(name), "title": name, "price": amount,
               "loc": "Sportson begagnat", "src": "Sportson", "url": "https://www.sportson.se" + slug,
               "size": size_label(name)}


WANTED = re.compile(r"\b(köpes|köpas|sökes|sökes|önskar köpa|letar efter|byteskoll|intressekoll)\b", re.I)


def facebook(profile):
    """Facebook Marketplace via the Apify REST API. Only runs when APIFY_TOKEN is set
    (the GitHub Action supplies it). No login/cookies — the actor handles that."""
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return
    payload = {"searchQuery": "racercykel", "sortBy": "creation_time_descend",
               "minPrice": BUDGET[0], "maxPrice": BUDGET[1], "marketplaceLocation": "stockholm",
               "radiusKm": 500, "categories": ["sports"], "maxItems": 60,
               "includeSeller": True, "flattenOutput": True}
    url = ("https://api.apify.com/v2/acts/memo23~facebook-marketplace-scraper-ppe/"
           f"run-sync-get-dataset-items?token={token}&timeout=240")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=280).read())
    for it in data:
        title = it.get("listingTitle") or it.get("title") or it.get("customTitle") or ""
        desc = it.get("description") or ""
        if not title or WANTED.search(title) or WANTED.search(desc[:250]):
            continue
        if not BRAND_OR_MODEL.search(title) or NOT_ROAD.search(title):
            continue
        text = f"{title} {desc}"
        if not size_ok(text, profile):
            continue
        price_raw = (it.get("price") or it.get("listingPrice.amount")
                     or (it.get("listingPrice") or {}).get("amount"))
        try:
            amount = int(float(price_raw))
        except (TypeError, ValueError):
            continue
        if not (BUDGET[0] <= amount <= BUDGET[1]):
            continue
        loc_raw = it.get("locationText") or it.get("location")
        loc = loc_raw.split(",")[0].strip() if isinstance(loc_raw, str) else ""
        item_url = it.get("itemUrl") or it.get("url") or it.get("facebookUrl") or ""
        yield {"id": "fb-" + str(it.get("id") or item_url or title), "brand": brand_of(title),
               "title": title, "price": amount, "loc": loc, "src": "Facebook",
               "url": item_url, "size": size_label(text)}


def collect(profile):
    items, errors = [], []
    for source in (blocket, happyride, sportson, facebook):
        try:
            items.extend(source(profile))
        except Exception as e:  # one dead source shouldn't kill the run
            errors.append(f"{source.__name__}: {e}")
    return items, errors


profile = "xl61" if "xl61" in sys.argv else "std"
BUDGET = BUDGETS[profile]
items, errors = collect(profile)

if "--json" in sys.argv:
    items.sort(key=lambda x: (x["brand"], x["price"]))
    print(json.dumps({"profile": profile, "items": items, "errors": errors}, ensure_ascii=False, indent=2))
    sys.exit(0)

# "new only" notifier mode
STATE = pathlib.Path(__file__).with_name(f"seen_{profile}.json")
seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
new = [it for it in items if it["id"] not in seen]
seen.update(it["id"] for it in items)
STATE.write_text(json.dumps(sorted(seen)))
if new:
    print(f"{len(new)} new match(es) [{profile}]:\n")
    for it in new:
        sz = f" · {it['size']}" if it["size"] else ""
        print(f"[{it['src']}] {it['title']} | {it['price']} kr | {it['loc']}{sz}\n  {it['url']}")
else:
    print(f"No new matches [{profile}].")
if errors:
    print("\nsource errors:", *errors, sep="\n  ")
