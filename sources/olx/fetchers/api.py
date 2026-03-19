"""OLX API fetcher — uses the JSON search API instead of Playwright scraping."""
import re
from datetime import date, datetime

import aiohttp

from data.schema import Listing
from sources.base import BaseFetcher
from sources.olx.location import resolve_location

OLX_SEARCH_API = "https://www.olx.in/api/relevance/v4/search"
CARS_CATEGORY_ID = 84


class OlxApiFetcher(BaseFetcher):
    needs_browser = False

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                    "Accept-Language": "en-IN,en;q=0.9",
                }
            )
        return self._session

    async def fetch_search(self, query: str, city: str, max_pages: int) -> list[Listing]:
        print(f"\nResolving location: {city!r}...")
        location = await resolve_location(city)
        print(f"  → {location.slug}_g{location.id}")

        session = self._get_session()
        listings: list[Listing] = []
        seen_ids: set[str] = set()

        for page_num in range(1, max_pages + 1):
            params = {
                "location_id": location.id,
                "keywords": query,
                "category_id": CARS_CATEGORY_ID,
                "page": page_num,
            }
            print(f"  API page {page_num}...")
            try:
                async with session.get(OLX_SEARCH_API, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
            except Exception as e:
                print(f"  Warning: API request failed on page {page_num}: {e}")
                break

            ads = data.get("data", {}).get("ads", [])
            if not ads:
                print(f"  No more ads on page {page_num}, stopping.")
                break

            new_count = 0
            for ad in ads:
                listing = _parse_ad(ad)
                if listing and listing.listing_id not in seen_ids:
                    seen_ids.add(listing.listing_id)
                    listings.append(listing)
                    new_count += 1

            print(f"  Page {page_num}: {new_count} new listings (total: {len(listings)})")

            # Stop if no next page signal
            if not data.get("data", {}).get("next_page"):
                break

        return listings

    async def fetch_details(self, listings: list[Listing]) -> list[Listing]:
        """API response already contains all fields — no second pass needed."""
        # Mark each listing as complete so the cache won't retry them
        for listing in listings:
            if listing.fuel_type is None:
                listing.fuel_type = "api"
        return listings

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def _parse_ad(ad: dict) -> Listing | None:
    try:
        listing_id = str(ad.get("id", ""))
        if not listing_id:
            return None

        url = ad.get("url", "")
        if not url.startswith("http"):
            url = f"https://www.olx.in{url}"

        title = ad.get("title", "")

        # Price: {"value": {"raw": 500000, "display": "₹5,00,000"}}
        price_raw = ad.get("price", {}).get("value", {}).get("raw")
        price = int(price_raw) if price_raw is not None else None

        # Location
        location = ad.get("location", {}).get("name", "")

        # Main image
        photos = ad.get("photos", [])
        image_url = photos[0].get("link", "") if photos else ""

        # Dates
        activation_date_str = ad.get("activation_date", "")
        posted_date = _parse_iso_date(activation_date_str)

        # Parse params list for year, km_driven, fuel, transmission, owners
        params = {p["key"]: p.get("value", {}).get("label", "") for p in ad.get("params", [])}

        year = _safe_int(params.get("year") or params.get("model_year"))
        km_driven = _parse_km(params.get("mileage") or params.get("km_driven", ""))
        fuel_type = (params.get("fuel_type") or params.get("fuel", "")).lower() or None
        transmission = (params.get("transmission", "")).lower() or None
        owners = _parse_owners(params.get("no_of_owners") or params.get("owners", ""))
        variant = params.get("variant") or None

        return Listing(
            listing_id=listing_id,
            platform="olx",
            url=url,
            title=title,
            price=price,
            year=year,
            km_driven=km_driven,
            fuel_type=fuel_type or "api",  # marks as complete
            transmission=transmission,
            owners=owners,
            variant=variant,
            location=location,
            image_url=image_url,
            scraped_at=datetime.now(),
            posted_date=posted_date,
        )
    except Exception as e:
        print(f"  Warning: failed to parse API ad: {e}")
        return None


def _parse_iso_date(text: str) -> date | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.rstrip("Z")).date()
    except ValueError:
        return None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_km(text: str) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[,\s]", "", str(text).lower().replace("km", "").replace("kms", ""))
    return int(cleaned) if cleaned.isdigit() else None


def _parse_owners(text: str) -> int | None:
    if not text:
        return None
    text = str(text).strip().lower()
    mapping = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
    if text in mapping:
        return mapping[text]
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None
