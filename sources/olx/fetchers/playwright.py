import asyncio

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from data.schema import Listing
from sources.base import BaseFetcher
from sources.olx.location import build_search_url, resolve_location
from sources.olx.parsers.search import parse_card
from sources.olx.parsers.detail import parse_detail

CONCURRENCY = 5


class OlxPlaywrightFetcher(BaseFetcher):
    needs_browser = True

    def __init__(self, context: BrowserContext):
        # Does NOT own browser lifecycle — CLI injects the context
        self._context = context

    async def fetch_search(self, query: str, city: str, max_pages: int) -> list[Listing]:
        print(f"\nResolving location: {city!r}...")
        location = await resolve_location(city)
        print(f"  → {location.slug}_g{location.id}")
        search_url = build_search_url(location.slug, location.id, query)
        print(f"  Search URL: {search_url}\n")

        page = await self._context.new_page()
        print("  Loading search page...")
        await page.goto(search_url, wait_until="commit", timeout=60000)

        try:
            await page.wait_for_selector('[data-aut-id="itemsList"]', timeout=20000)
        except Exception:
            print("  No listings found, stopping.")
            await page.close()
            return []

        seen_ids: set[str] = set()
        listings: list[Listing] = []

        for load_num in range(1, max_pages + 1):
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            items_list = soup.find(attrs={"data-aut-id": "itemsList"})
            if not items_list:
                break

            cards = items_list.find_all(attrs={"data-aut-id": "itemBox2"})
            new_listings = []
            for card in cards:
                listing = parse_card(card)
                if listing and listing.listing_id not in seen_ids:
                    seen_ids.add(listing.listing_id)
                    new_listings.append(listing)

            listings.extend(new_listings)
            print(f"  Load {load_num}: {len(new_listings)} new listings (total: {len(listings)})")

            load_more_btn = await page.query_selector('[data-aut-id="btnLoadMore"]')
            if not load_more_btn:
                break

            await load_more_btn.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # networkidle may timeout on slow connections; proceed anyway

        await page.close()
        return listings

    async def fetch_details(self, listings: list[Listing]) -> list[Listing]:
        semaphore = asyncio.Semaphore(CONCURRENCY)
        total = len(listings)

        async def fetch_one(listing: Listing, index: int) -> Listing:
            async with semaphore:
                print(f"  Detail [{index + 1}/{total}] {listing.listing_id}")
                try:
                    page = await self._context.new_page()
                    await page.goto(listing.url, wait_until="commit", timeout=60000)

                    if listing.listing_id not in page.url:
                        print(f"  Skipping {listing.listing_id} — redirected to {page.url}")
                        await page.close()
                        listing.fuel_type = "unavailable"
                        return listing

                    await page.wait_for_selector('[data-aut-id="leftPanel"]', timeout=20000)
                    html = await page.content()
                    await page.close()
                    return parse_detail(listing, html)
                except Exception as e:
                    print(f"  Warning: detail scrape failed for {listing.listing_id}: {e}")
                    return listing

        tasks = [fetch_one(l, i) for i, l in enumerate(listings)]
        return await asyncio.gather(*tasks)
