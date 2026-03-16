import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup
from playwright.async_api import Page

from data.schema import Listing

BASE_URL = "https://www.olx.in"


async def scrape_search_pages(page: Page, search_url: str, max_pages: int = 10) -> list[Listing]:
    """
    Scrape all listing cards from search result pages (Pass 1).
    Clicks "Load More" until all listings are loaded or max_pages is reached.
    """
    print("  Loading search page...")
    await page.goto(search_url, wait_until="commit", timeout=60000)

    try:
        await page.wait_for_selector('[data-aut-id="itemsList"]', timeout=20000)
    except Exception:
        print("  No listings found, stopping.")
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
            listing = _parse_card(card)
            if listing and listing.listing_id not in seen_ids:
                seen_ids.add(listing.listing_id)
                new_listings.append(listing)

        listings.extend(new_listings)
        print(f"  Load {load_num}: {len(new_listings)} new listings (total: {len(listings)})")

        load_more_btn = await page.query_selector('[data-aut-id="btnLoadMore"]')
        if not load_more_btn:
            break

        await load_more_btn.click()
        # Wait for new cards to appear
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass  # networkidle may timeout on slow connections; proceed anyway

    return listings


def _parse_card(card) -> Listing | None:
    try:
        link_tag = card.find("a", href=True)
        if not link_tag:
            return None

        relative_url = link_tag["href"]
        full_url = BASE_URL + relative_url
        listing_id = _extract_listing_id(relative_url)
        if not listing_id:
            return None

        price_tag = card.find(attrs={"data-aut-id": "itemPrice"})
        price = _parse_price(price_tag.get_text(strip=True)) if price_tag else None

        title_tag = card.find(attrs={"data-aut-id": "itemTitle"})
        title = title_tag.get_text(strip=True) if title_tag else None

        subtitle_tag = card.find(attrs={"data-aut-id": "itemSubTitle"})
        year, km_driven = None, None
        if subtitle_tag:
            year, km_driven = _parse_subtitle(subtitle_tag.get("title", ""))

        location_tag = card.find(attrs={"data-aut-id": "itemDetails"})
        location, posted_date = None, None
        if location_tag:
            spans = location_tag.find_all("span", recursive=False)
            # itemDetails has nested spans; get the direct text spans
            all_spans = location_tag.find_all("span")
            texts = [s.get_text(strip=True) for s in all_spans if s.get_text(strip=True)]
            if texts:
                location = texts[0]
            # posted date is the last non-empty text
            if len(texts) > 1:
                posted_date = _parse_relative_date(texts[-1])

        img_tag = card.find("img")
        image_url = img_tag.get("src", "") if img_tag else ""

        return Listing(
            listing_id=listing_id,
            platform="olx",
            url=full_url,
            title=title,
            price=price,
            year=year,
            km_driven=km_driven,
            location=location,
            image_url=image_url,
            scraped_at=datetime.now(),
            posted_date=posted_date,
        )
    except Exception as e:
        print(f"  Warning: failed to parse card: {e}")
        return None


def _extract_listing_id(url: str) -> str | None:
    match = re.search(r"iid-(\d+)", url)
    return match.group(1) if match else None


def _parse_subtitle(text: str) -> tuple[int | None, int | None]:
    """Parse '2018 - 91,000 km' → (2018, 91000)."""
    parts = text.split(" - ", 1)
    year = int(parts[0].strip()) if len(parts) >= 1 and parts[0].strip().isdigit() else None
    km = None
    if len(parts) == 2:
        km_str = re.sub(r"[,\s]", "", parts[1].lower().replace("km", ""))
        km = int(km_str) if km_str.isdigit() else None
    return year, km


def _parse_price(text: str) -> int | None:
    cleaned = re.sub(r"[₹,\s]", "", text)
    return int(cleaned) if cleaned.isdigit() else None


def _parse_relative_date(text: str) -> date | None:
    text = text.strip().lower()
    today = date.today()
    if text == "today":
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    match = re.match(r"(\d+)\s+days?\s+ago", text)
    if match:
        return today - timedelta(days=int(match.group(1)))
    # Try direct date parse (e.g. "14-MAR-26")
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.upper(), fmt.upper()).date()
        except ValueError:
            continue
    return None
