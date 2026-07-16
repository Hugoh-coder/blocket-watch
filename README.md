# Bike watch — used road bikes in Sweden

Live sites that list used road bikes (landsvägscyklar) from **Trek, Specialized, Canyon,
Bianchi**, 10 000–25 000 kr, across Blocket, Happyride, Sportson Begagnat and Facebook
Marketplace. Two size profiles, each its own page:

- **`docs/cyklar.html`** — L / XL / 58 cm (rejects any explicit 56 cm)
- **`docs/cyklar-xl.html`** — XL / 60–62 cm (taller rider)
- **`docs/index.html`** — landing that links both

Served by **GitHub Pages** from `/docs`, refreshed every morning by a **GitHub Action**.

## How it works

- `watch.py` scrapes the sources and prints matches. Size lives in free text (except
  Happyride's native size filter), so it's parsed with regex.
  - `uv run watch.py` — profile `std` (L/XL/58), prints only NEW ads (notifier mode)
  - `uv run watch.py xl61` — profile `xl61` (XL/60–62)
  - add `--json` to print ALL matches as JSON (used to build the site)
  - Facebook runs only when `APIFY_TOKEN` is set (via the Apify REST API, no login/cookies).
- `build_sites.py` reads `std.json` / `xl61.json` and writes the three pages into `docs/`.
- `.github/workflows/refresh.yml` runs both, rebuilds `docs/`, commits, daily at 07:00 CEST.

## Refresh manually

```sh
uv run watch.py --json > std.json
uv run watch.py xl61 --json > xl61.json
python3 build_sites.py
```

## Setup (one-time)

1. Push this repo to GitHub.
2. Settings → Pages → Source: **Deploy from a branch**, branch `main`, folder `/docs`.
3. Settings → Secrets and variables → Actions → add `APIFY_TOKEN` (from apify.com) to
   enable the Facebook source. Omit it and the site still works with the other 3 sources.
4. Actions tab → run **Refresh bike listings** once to populate.

## Known limits

- Facebook coverage is Stockholm + 500 km (the actor's other Swedish city slugs don't
  resolve); the other three sources are national.
- Scrapers are unofficial (Blocket API wrapper, HTML parsing) — a site redesign can break
  a source; the run isolates failures so one dead source won't stop the others.
- Snapshots reflect the moment of the run; the daily Action keeps them current.
