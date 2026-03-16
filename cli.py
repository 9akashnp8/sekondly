import asyncio
from datetime import datetime
from pathlib import Path

import click
from playwright.async_api import async_playwright

from analysis.kpis import compute_kpis
from analysis.scorer import score_listings
from data import store
from report.generator import generate_report
from scraper.location import build_search_url, resolve_location
from scraper.search import scrape_search_pages
from scraper.detail import scrape_details

# Injected into every page before any scripts run.
# Removes JS signals that OLX uses to detect headless/automated browsers.
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
window.chrome = { runtime: {} };
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
  params.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : origQuery(params);
"""


@click.command()
@click.option("--model",     "-m", required=True,  help="Car model to search (e.g. 'Honda City')")
@click.option("--city",      "-c", required=True,  help="City name (e.g. 'Kochi')")
@click.option("--max-pages",       default=5,      show_default=True, help="Max search result pages to scrape")
@click.option("--output",    "-o", default=None,   help="Output HTML file path (default: auto-named)")
@click.option("--no-cache",        is_flag=True,   default=False, help="Ignore cached listing details and re-scrape")
@click.option("--headless",        is_flag=True,   default=False, help="Run browser in headless mode (may be blocked by OLX)")
def main(model: str, city: str, max_pages: int, output: str | None, no_cache: bool, headless: bool):
    """OLX Ads Analyzer — scrape, score, and report on used car listings."""
    asyncio.run(_run(model, city, max_pages, output, no_cache, headless))


async def _run(model: str, city: str, max_pages: int, output: str | None, no_cache: bool, headless: bool):
    store.init_db()

    # --- Resolve location ---
    print(f"\nResolving location: {city!r}...")
    try:
        location_slug, location_id = await resolve_location(city)
    except ValueError as e:
        raise click.ClickException(str(e))
    print(f"  → {location_slug}_g{location_id}")

    search_url = build_search_url(location_slug, location_id, model)
    print(f"  Search URL: {search_url}\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-http2",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        await context.add_init_script(_STEALTH_SCRIPT)

        page = await context.new_page()

        # --- Pass 1: scrape search pages ---
        print("Pass 1: Scraping search pages...")
        listings = await scrape_search_pages(page, search_url, max_pages=max_pages)
        await page.close()

        if not listings:
            raise click.ClickException("No listings found. Try a different model or city.")

        print(f"  Total listings found: {len(listings)}")

        # Upsert Pass 1 data into cache
        for l in listings:
            store.upsert(l)

        # --- Pass 2: scrape detail pages ---
        listing_ids = [l.listing_id for l in listings]

        if no_cache:
            to_detail = listings
        else:
            incomplete_ids = set(store.get_incomplete_ids(listing_ids))
            to_detail = [l for l in listings if l.listing_id in incomplete_ids]

        if to_detail:
            print(f"\nPass 2: Scraping details for {len(to_detail)} listings...")
            detailed = await scrape_details(context, to_detail)
            for l in detailed:
                store.upsert(l)
        else:
            print("\nPass 2: All listings already cached, skipping detail scrape.")

        await browser.close()

    # --- Load full data from cache ---
    full_listings = store.get_all(listing_ids)
    print(f"\nLoaded {len(full_listings)} listings from cache.")

    # --- Analysis ---
    print("Computing KPIs...")
    kpis = compute_kpis(full_listings)

    print("Scoring listings...")
    scored = score_listings(full_listings)

    # --- Report ---
    if output:
        output_path = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = model.lower().replace(" ", "_")
        safe_city = city.lower().replace(" ", "_")
        output_path = Path(f"report_{safe_model}_{safe_city}_{ts}.html")

    generate_report(
        query=model,
        city=city,
        kpis=kpis,
        scored=scored,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()
