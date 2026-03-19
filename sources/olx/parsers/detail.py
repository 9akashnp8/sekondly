"""Pure parsing functions for OLX listing detail pages (no Playwright dependency)."""
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from data.schema import Listing


def parse_detail(listing: Listing, html: str) -> Listing:
    soup = BeautifulSoup(html, "html.parser")

    panel = soup.find(attrs={"data-aut-id": "leftPanel"})
    if not panel:
        return listing

    # --- Fuel, km, transmission (stable data-aut-id attributes) ---
    fuel_tag = panel.find(attrs={"data-aut-id": "itemAttribute_fuel"})
    fuel_type = fuel_tag.get_text(strip=True).lower() if fuel_tag else None

    mileage_tag = panel.find(attrs={"data-aut-id": "itemAttribute_mileage"})
    km_driven = parse_km(mileage_tag.get_text(strip=True)) if mileage_tag else None

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
        kv = parse_overview_kvs(panel)
        if "owner" in kv:
            owners = parse_owners(kv["owner"])
        if "posting date" in kv:
            parsed = parse_date(kv["posting date"])
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


def parse_overview_kvs(container) -> dict[str, str]:
    """
    Scan for overview label/value div pairs anywhere in container.
    Returns a dict of lowercased label → value text.
    """
    if container is None:
        return {}
    result = {}
    for item in container.find_all("div"):
        child_divs = [c for c in item.children if getattr(c, "name", None) == "div"]
        if len(child_divs) != 2:
            continue
        label = child_divs[0].get_text(strip=True)
        value = child_divs[1].get_text(strip=True)
        if label and value and len(label) < 30:
            result[label.lower()] = value
    return result


def parse_km(text: str) -> int | None:
    cleaned = re.sub(r"[,\s]", "", text.lower().replace("km", "").replace("kms", ""))
    return int(cleaned) if cleaned.isdigit() else None


def parse_owners(text: str) -> int | None:
    text = text.strip().lower()
    mapping = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
    if text in mapping:
        return mapping[text]
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None


def parse_date(text: str) -> date | None:
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.upper(), fmt.upper()).date()
        except ValueError:
            continue
    return None
