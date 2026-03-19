"""Pure parsing functions for OLX search result cards (no Playwright dependency)."""
import re
from datetime import date, datetime, timedelta

from data.schema import Listing

BASE_URL = "https://www.olx.in"


def parse_card(card) -> Listing | None:
    try:
        link_tag = card.find("a", href=True)
        if not link_tag:
            return None

        relative_url = link_tag["href"]
        full_url = BASE_URL + relative_url
        listing_id = extract_listing_id(relative_url)
        if not listing_id:
            return None

        price_tag = card.find(attrs={"data-aut-id": "itemPrice"})
        price = parse_price(price_tag.get_text(strip=True)) if price_tag else None

        title_tag = card.find(attrs={"data-aut-id": "itemTitle"})
        title = title_tag.get_text(strip=True) if title_tag else None

        subtitle_tag = card.find(attrs={"data-aut-id": "itemSubTitle"})
        year, km_driven = None, None
        if subtitle_tag:
            year, km_driven = parse_subtitle(subtitle_tag.get("title", ""))

        location_tag = card.find(attrs={"data-aut-id": "itemDetails"})
        location, posted_date = None, None
        if location_tag:
            all_spans = location_tag.find_all("span")
            texts = [s.get_text(strip=True) for s in all_spans if s.get_text(strip=True)]
            if texts:
                location = texts[0]
            if len(texts) > 1:
                posted_date = parse_relative_date(texts[-1])

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


def extract_listing_id(url: str) -> str | None:
    match = re.search(r"iid-(\d+)", url)
    return match.group(1) if match else None


def parse_subtitle(text: str) -> tuple[int | None, int | None]:
    """Parse '2018 - 91,000 km' → (2018, 91000)."""
    parts = text.split(" - ", 1)
    year = int(parts[0].strip()) if len(parts) >= 1 and parts[0].strip().isdigit() else None
    km = None
    if len(parts) == 2:
        km_str = re.sub(r"[,\s]", "", parts[1].lower().replace("km", ""))
        km = int(km_str) if km_str.isdigit() else None
    return year, km


def parse_price(text: str) -> int | None:
    cleaned = re.sub(r"[₹,\s]", "", text)
    return int(cleaned) if cleaned.isdigit() else None


def parse_relative_date(text: str) -> date | None:
    text = text.strip().lower()
    today = date.today()
    if text == "today":
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    match = re.match(r"(\d+)\s+days?\s+ago", text)
    if match:
        return today - timedelta(days=int(match.group(1)))
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.upper(), fmt.upper()).date()
        except ValueError:
            continue
    return None
