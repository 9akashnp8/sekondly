from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Listing:
    # Pass 1 — search page
    listing_id: str
    platform: str
    url: str
    title: str
    price: int
    location: str
    image_url: str
    scraped_at: datetime

    # Pass 2 — detail page
    year: Optional[int] = None
    km_driven: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    owners: Optional[int] = None
    variant: Optional[str] = None
    posted_date: Optional[date] = None
    description: Optional[str] = None

    def is_complete(self) -> bool:
        """True if Pass 2 detail scrape has been done."""
        return self.fuel_type is not None
