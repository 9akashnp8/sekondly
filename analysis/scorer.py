from dataclasses import dataclass
from datetime import date

import pandas as pd

from data.schema import Listing


@dataclass
class ScoredListing:
    listing: Listing
    score: float          # 0–100, higher = better deal
    verdict: str          # "Great Deal", "Fair Price", "Overpriced"
    reasons: list[str]    # human-readable explanation bullets


def score_listings(listings: list[Listing]) -> list[ScoredListing]:
    df = _build_reference_df(listings)
    scored = [_score_one(l, df) for l in listings if l.price and l.price > 0 and l.fuel_type != "unavailable"]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def _score_one(listing: Listing, ref_df: pd.DataFrame) -> ScoredListing:
    score = 50.0  # neutral baseline
    reasons: list[str] = []

    # --- Price vs. median for comparable bucket ---
    bucket = ref_df[
        (ref_df["year"] == listing.year) &
        (ref_df["fuel_type"] == listing.fuel_type) &
        (ref_df["transmission"] == listing.transmission)
    ]
    if len(bucket) >= 3:
        median_price = bucket["price"].median()
        pct_diff = (listing.price - median_price) / median_price * 100
        price_score = max(-30, min(30, -pct_diff * 0.6))  # ±30 pts
        score += price_score
        if pct_diff < -10:
            reasons.append(f"{abs(pct_diff):.0f}% below median for {listing.year} {listing.fuel_type} {listing.transmission}")
        elif pct_diff > 10:
            reasons.append(f"{abs(pct_diff):.0f}% above median for {listing.year} {listing.fuel_type} {listing.transmission}")
        else:
            reasons.append(f"Priced near market median for {listing.year} {listing.fuel_type} {listing.transmission}")
    else:
        # Fall back to overall median
        overall_median = ref_df["price"].median()
        if pd.notna(overall_median) and overall_median > 0:
            pct_diff = (listing.price - overall_median) / overall_median * 100
            score += max(-20, min(20, -pct_diff * 0.4))
            reasons.append("Limited comparable listings — compared against overall median")

    # --- Km vs expected for age ---
    if listing.km_driven and listing.year:
        age = date.today().year - listing.year
        expected_km = age * 12000  # ~12,000 km/year is typical India average
        if expected_km > 0:
            km_ratio = listing.km_driven / expected_km
            if km_ratio < 0.6:
                score += 10
                reasons.append(f"Low mileage for age ({listing.km_driven:,} km vs ~{expected_km:,} expected)")
            elif km_ratio > 1.5:
                score -= 10
                reasons.append(f"High mileage for age ({listing.km_driven:,} km vs ~{expected_km:,} expected)")

    # --- Owner count ---
    if listing.owners:
        if listing.owners == 1:
            score += 8
            reasons.append("1st owner")
        elif listing.owners == 2:
            score += 2
        elif listing.owners >= 3:
            score -= 8
            reasons.append(f"{listing.owners} previous owners")

    # --- Listing recency ---
    if listing.posted_date:
        days_old = (date.today() - listing.posted_date).days
        if days_old > 30:
            score -= 5
            reasons.append(f"Listed {days_old} days ago — may indicate issues or inflexible pricing")

    score = max(0.0, min(100.0, score))

    if score >= 65:
        verdict = "Great Deal"
    elif score >= 40:
        verdict = "Fair Price"
    else:
        verdict = "Overpriced"

    return ScoredListing(listing=listing, score=round(score, 1), verdict=verdict, reasons=reasons)


def _build_reference_df(listings: list[Listing]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "listing_id": l.listing_id,
            "price": l.price,
            "year": l.year,
            "km_driven": l.km_driven,
            "fuel_type": l.fuel_type,
            "transmission": l.transmission,
            "owners": l.owners,
        }
        for l in listings
        if l.price and l.price > 0
    ])
