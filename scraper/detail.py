import asyncio
import re
from datetime import date, datetime

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from data.schema import Listing

BASE_URL = "https://www.olx.in"
CONCURRENCY = 5


async def scrape_details(context: BrowserContext, listings: list[Listing]) -> list[Listing]:
    """
    Pass 2: visit each listing's detail page and fill in missing fields.
    Runs CONCURRENCY requests in parallel.
    """
    semaphore = asyncio.Semaphore(CONCURRENCY)
    total = len(listings)

    async def fetch_one(listing: Listing, index: int) -> Listing:
        async with semaphore:
            print(f"  Detail [{index + 1}/{total}] {listing.listing_id}")
            try:
                page = await context.new_page()
                await page.goto(listing.url, wait_until="commit", timeout=60000)

                # If redirected away from the listing (e.g. ad deleted/sold),
                # the URL will no longer contain the listing ID.
                if listing.listing_id not in page.url:
                    print(f"  Skipping {listing.listing_id} — redirected to {page.url}")
                    await page.close()
                    listing.fuel_type = "unavailable"  # mark as processed so cache doesn't retry
                    return listing

                await page.wait_for_selector('[data-aut-id="leftPanel"]', timeout=20000)
                html = await page.content()
                await page.close()
                return _parse_detail(listing, html)
            except Exception as e:
                print(f"  Warning: detail scrape failed for {listing.listing_id}: {e}")
                return listing

    tasks = [fetch_one(l, i) for i, l in enumerate(listings)]
    return await asyncio.gather(*tasks)


def _parse_detail(listing: Listing, html: str) -> Listing:
    soup = BeautifulSoup(html, "html.parser")

    panel = soup.find(attrs={"data-aut-id": "leftPanel"})
    if not panel:
        return listing

    # --- Fuel, km, transmission (stable data-aut-id attributes) ---
    fuel_tag = panel.find(attrs={"data-aut-id": "itemAttribute_fuel"})
    fuel_type = fuel_tag.get_text(strip=True).lower() if fuel_tag else None

    mileage_tag = panel.find(attrs={"data-aut-id": "itemAttribute_mileage"})
    km_driven = _parse_km(mileage_tag.get_text(strip=True)) if mileage_tag else None

    tx_tag = panel.find(attrs={"data-aut-id": "itemAttribute_transmission"})
    transmission = tx_tag.get_text(strip=True).lower() if tx_tag else None

    # --- Variant: next sibling div after itemTitle (positional, class-agnostic) ---
    title_tag = panel.find(attrs={"data-aut-id": "itemTitle"})
    variant = None
    if title_tag:
        sibling = title_tag.find_next_sibling("div")
        if sibling:
            variant = sibling.get_text(strip=True) or None

    # --- Overview key-value pairs: parse by label text, not class ---
    owners = None
    posted_date = listing.posted_date  # keep card value as fallback
    overview_section = panel.find(attrs={"data-aut-id": "adOverview"})
    if overview_section:
        kv = _parse_overview_kvs(panel)
        if "owner" in kv:
            owners = _parse_owners(kv["owner"])
        if "posting date" in kv:
            parsed = _parse_date(kv["posting date"])
            if parsed:
                posted_date = parsed

    # --- Description: concatenate all itemDescripton divs (note OLX typo) ---
    desc_tags = panel.find_all(attrs={"data-aut-id": "itemDescripton"})
    description = "\n".join(d.get_text(strip=True) for d in desc_tags if d.get_text(strip=True))

    listing.fuel_type = fuel_type or listing.fuel_type
    listing.km_driven = km_driven or listing.km_driven
    listing.transmission = transmission or listing.transmission
    listing.variant = variant or listing.variant
    listing.owners = owners if owners is not None else listing.owners
    listing.posted_date = posted_date
    listing.description = description or listing.description

    return listing


def _parse_overview_kvs(container) -> dict[str, str]:
    """
    Scan for overview label/value div pairs anywhere in container.
    Matches divs whose direct children are exactly 2 divs, each with short plain text.
    Returns a dict of lowercased label → value text.
    """
    if container is None:
        return {}
    result = {}
    for item in container.find_all("div"):
        # Only look at direct div children (not nested descendants)
        child_divs = [c for c in item.children if getattr(c, "name", None) == "div"]
        if len(child_divs) != 2:
            continue
        label = child_divs[0].get_text(strip=True)
        value = child_divs[1].get_text(strip=True)
        # Sanity check: label should be short and non-empty, value non-empty
        if label and value and len(label) < 30:
            result[label.lower()] = value
    return result


def _parse_km(text: str) -> int | None:
    cleaned = re.sub(r"[,\s]", "", text.lower().replace("km", "").replace("kms", ""))
    return int(cleaned) if cleaned.isdigit() else None


def _parse_owners(text: str) -> int | None:
    text = text.strip().lower()
    mapping = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
    if text in mapping:
        return mapping[text]
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_date(text: str) -> date | None:
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.upper(), fmt.upper()).date()
        except ValueError:
            continue
    return None
