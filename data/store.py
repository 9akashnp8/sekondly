import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from data.schema import Listing

DB_PATH = Path("olx_cache.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                listing_id   TEXT PRIMARY KEY,
                platform     TEXT NOT NULL,
                url          TEXT NOT NULL,
                title        TEXT,
                price        INTEGER,
                location     TEXT,
                image_url    TEXT,
                scraped_at   TEXT,
                year         INTEGER,
                km_driven    INTEGER,
                fuel_type    TEXT,
                transmission TEXT,
                owners       INTEGER,
                variant      TEXT,
                posted_date  TEXT,
                description  TEXT
            )
        """)


def upsert(listing: Listing) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO listings VALUES (
                :listing_id, :platform, :url, :title, :price, :location,
                :image_url, :scraped_at, :year, :km_driven, :fuel_type,
                :transmission, :owners, :variant, :posted_date, :description
            )
            ON CONFLICT(listing_id) DO UPDATE SET
                title        = excluded.title,
                price        = excluded.price,
                location     = excluded.location,
                image_url    = excluded.image_url,
                scraped_at   = excluded.scraped_at,
                year         = COALESCE(excluded.year, listings.year),
                km_driven    = COALESCE(excluded.km_driven, listings.km_driven),
                fuel_type    = COALESCE(excluded.fuel_type, listings.fuel_type),
                transmission = COALESCE(excluded.transmission, listings.transmission),
                owners       = COALESCE(excluded.owners, listings.owners),
                variant      = COALESCE(excluded.variant, listings.variant),
                posted_date  = COALESCE(excluded.posted_date, listings.posted_date),
                description  = COALESCE(excluded.description, listings.description)
        """, _to_row(listing))


def get_incomplete_ids(listing_ids: list[str]) -> list[str]:
    """Return IDs from the given list that don't yet have detail data."""
    if not listing_ids:
        return []
    with _connect() as conn:
        placeholders = ",".join("?" * len(listing_ids))
        rows = conn.execute(
            f"SELECT listing_id FROM listings WHERE listing_id IN ({placeholders}) AND fuel_type IS NULL",
            listing_ids,
        ).fetchall()
    return [r["listing_id"] for r in rows]


def get_all(listing_ids: list[str]) -> list[Listing]:
    if not listing_ids:
        return []
    with _connect() as conn:
        placeholders = ",".join("?" * len(listing_ids))
        rows = conn.execute(
            f"SELECT * FROM listings WHERE listing_id IN ({placeholders})",
            listing_ids,
        ).fetchall()
    return [_from_row(r) for r in rows]


def _to_row(l: Listing) -> dict:
    return {
        "listing_id": l.listing_id,
        "platform": l.platform,
        "url": l.url,
        "title": l.title,
        "price": l.price,
        "location": l.location,
        "image_url": l.image_url,
        "scraped_at": l.scraped_at.isoformat() if l.scraped_at else None,
        "year": l.year,
        "km_driven": l.km_driven,
        "fuel_type": l.fuel_type,
        "transmission": l.transmission,
        "owners": l.owners,
        "variant": l.variant,
        "posted_date": l.posted_date.isoformat() if l.posted_date else None,
        "description": l.description,
    }


def _from_row(r: sqlite3.Row) -> Listing:
    return Listing(
        listing_id=r["listing_id"],
        platform=r["platform"],
        url=r["url"],
        title=r["title"],
        price=r["price"],
        location=r["location"],
        image_url=r["image_url"],
        scraped_at=datetime.fromisoformat(r["scraped_at"]) if r["scraped_at"] else datetime.now(),
        year=r["year"],
        km_driven=r["km_driven"],
        fuel_type=r["fuel_type"],
        transmission=r["transmission"],
        owners=r["owners"],
        variant=r["variant"],
        posted_date=date.fromisoformat(r["posted_date"]) if r["posted_date"] else None,
        description=r["description"],
    )
