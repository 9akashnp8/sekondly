# Sekondly

Market intelligence for second-hand car listings. Sekondly fetches listings from OLX.in, scores each deal against real market data, and generates a self-contained HTML report — no server required.

---

## What it does

1. **Fetches listings** for a car model + city (e.g. "Honda City" in "Kochi") across multiple search pages
2. **Enriches** each listing with detail-page data: year, km driven, fuel type, transmission, owners, variant
3. **Computes market KPIs**: price distribution, median/mean/min/max, breakdowns by year, fuel, transmission, and owner count
4. **Scores every listing** (0–100) against comparable listings in the same year/fuel/transmission bucket, adjusted for mileage, owner history, and listing age
5. **Outputs a self-contained HTML report** with interactive charts and a filterable listings table — open in any browser, share as a single file

---

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/your-username/sekondly
cd sekondly
uv sync
playwright install chromium
```

Run your first report:

```bash
uv run python cli.py --model "Honda City" --city "Kochi"
```

This opens a visible Chromium window (OLX blocks headless browsers), fetches up to 5 pages of results, and writes `report_honda_city_kochi_<timestamp>.html`.

---

## CLI reference

```
Usage: cli.py [OPTIONS]

  Sekondly — market intelligence for second-hand car listings.

Options:
  -m, --model TEXT         Car model to search (e.g. 'Honda City')  [required]
  -c, --city TEXT          City name (e.g. 'Kochi')                 [required]
  --max-pages INTEGER      Max search result pages to fetch  [default: 5]
  -o, --output TEXT        Output HTML file path (default: auto-named)
  --no-cache               Ignore cached listing details and re-fetch
  --headless               Run browser in headless mode (Playwright only)
  -s, --source [olx]       Data source to use  [default: olx]
  -f, --fetcher TEXT       Fetcher to use: 'playwright' or 'api'  [default: playwright]
```

### Examples

```bash
# Basic run
uv run python cli.py -m "Maruti Swift" -c "Bangalore"

# Fetch more pages, custom output file
uv run python cli.py -m "Virtus" -c "Mumbai" --max-pages 10 -o virtus_report.html

# Force re-fetch (ignore SQLite cache)
uv run python cli.py -m "Swift" -c "Delhi" --no-cache

# Use the API fetcher — no browser needed, faster
uv run python cli.py -m "Honda City" -c "Kochi" --fetcher api
```

---

## Deal scoring

Each listing is scored 0–100 and assigned a verdict:

| Score | Verdict |
|-------|---------|
| 65–100 | Great Deal |
| 40–64  | Fair Price |
| 0–39   | Overpriced |

The score is built from four signals:

- **Price vs. bucket median** — compares against listings with the same year, fuel type, and transmission (falls back to overall median if fewer than 3 comparables exist)
- **Mileage for age** — flags low (<60% of expected) or high (>150%) km relative to ~12,000 km/year typical usage
- **Owner count** — 1st owner adds points; 3+ owners deducts
- **Listing age** — listings posted 30+ days ago score slightly lower

The report shows the human-readable reasons behind each score.

---

## Architecture

```
cli.py              Entry point — Click CLI, Playwright browser lifecycle
orchestrator.py     Source-agnostic two-pass pipeline
sources/
  base.py           BaseFetcher + BaseSource ABCs
  olx/
    location.py     City name → OLX location slug (via OLX API)
    fetchers/
      playwright.py Browser-based fetcher (needs_browser=True)
      api.py        HTTP API fetcher via aiohttp (needs_browser=False)
    parsers/
      search.py     Search-page parser → Listing stubs
      detail.py     Detail-page parser → enriched Listings
data/
  schema.py         Listing dataclass (pass 1 + pass 2 fields)
  store.py          SQLite cache — upsert, get_incomplete_ids
analysis/
  kpis.py           MarketKPIs computation with pandas
  scorer.py         Per-listing deal scoring + verdicts
report/
  generator.py      Jinja2 → self-contained HTML
  templates/        Report template with Chart.js charts
```

The fetcher abstraction (`BaseFetcher`) lets new data sources be added without touching the pipeline. The `needs_browser` flag means the CLI only launches Playwright when the chosen fetcher actually requires it.

---

## Caching

Listing details are cached in `olx_cache.db` (SQLite). On subsequent runs for the same model+city, only new or incomplete listings are re-fetched. Use `--no-cache` to force a full re-fetch.

---

## Known limitations

- **Headless mode is blocked by OLX** — the Playwright fetcher must run with a visible browser. The `--headless` flag exists but may not work reliably.
- The API fetcher (`--fetcher api`) is faster and headless but may be less reliable depending on OLX API changes.
- Currently only OLX.in is supported as a data source.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| playwright | Browser automation for search + detail scraping |
| aiohttp | Async HTTP for the API-based fetcher |
| beautifulsoup4 | HTML parsing |
| pandas | KPI aggregation and scoring |
| jinja2 | HTML report templating |
| click | CLI interface |
