from dataclasses import dataclass

import pandas as pd

from data.schema import Listing


@dataclass
class MarketKPIs:
    total_listings: int
    price_min: int
    price_max: int
    price_mean: int
    price_median: int

    by_year: list[dict]           # [{year, count, median_price, avg_km}]
    by_fuel: list[dict]           # [{fuel_type, count, median_price}]
    by_transmission: list[dict]   # [{transmission, count, median_price}]
    by_owners: list[dict]         # [{owners, count, median_price}]
    price_distribution: list[int] # raw prices for histogram


def compute_kpis(listings: list[Listing]) -> MarketKPIs:
    df = _to_df(listings)

    price_dist = df["price"].dropna().astype(int).tolist()

    by_year = (
        df.groupby("year", dropna=True)
        .agg(count=("price", "count"), median_price=("price", "median"), avg_km=("km_driven", "mean"))
        .reset_index()
        .sort_values("year")
        .assign(median_price=lambda x: x["median_price"].astype(int), avg_km=lambda x: x["avg_km"].fillna(0).astype(int))
        .to_dict("records")
    )

    by_fuel = (
        df[df["fuel_type"].notna()]
        .groupby("fuel_type")
        .agg(count=("price", "count"), median_price=("price", "median"))
        .reset_index()
        .assign(median_price=lambda x: x["median_price"].astype(int))
        .to_dict("records")
    )

    by_transmission = (
        df[df["transmission"].notna()]
        .groupby("transmission")
        .agg(count=("price", "count"), median_price=("price", "median"))
        .reset_index()
        .assign(median_price=lambda x: x["median_price"].astype(int))
        .to_dict("records")
    )

    by_owners = (
        df[df["owners"].notna()]
        .groupby("owners")
        .agg(count=("price", "count"), median_price=("price", "median"))
        .reset_index()
        .assign(owners=lambda x: x["owners"].astype(int), median_price=lambda x: x["median_price"].astype(int))
        .sort_values("owners")
        .to_dict("records")
    )

    valid = df["price"].dropna()
    return MarketKPIs(
        total_listings=len(df),
        price_min=int(valid.min()) if len(valid) else 0,
        price_max=int(valid.max()) if len(valid) else 0,
        price_mean=int(valid.mean()) if len(valid) else 0,
        price_median=int(valid.median()) if len(valid) else 0,
        by_year=by_year,
        by_fuel=by_fuel,
        by_transmission=by_transmission,
        by_owners=by_owners,
        price_distribution=price_dist,
    )


def _to_df(listings: list[Listing]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "listing_id": l.listing_id,
            "price": l.price,
            "year": l.year,
            "km_driven": l.km_driven,
            "fuel_type": l.fuel_type,
            "transmission": l.transmission,
            "owners": l.owners,
            "posted_date": l.posted_date,
        }
        for l in listings
        if l.price and l.price > 0 and l.fuel_type != "unavailable"
    ])
