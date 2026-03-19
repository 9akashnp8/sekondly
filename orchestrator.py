"""Source-agnostic two-pass pipeline extracted from cli._run()."""
from pathlib import Path

import click

from analysis.kpis import compute_kpis
from analysis.scorer import score_listings
from data import store
from report.generator import generate_report
from sources.base import BaseFetcher, BaseSource


async def run_pipeline(
    source: BaseSource,
    fetcher: BaseFetcher,
    query: str,
    city: str,
    max_pages: int,
    no_cache: bool,
    output_path: Path,
) -> None:
    store.init_db()

    # --- Pass 1: fetch search listings ---
    # Location resolution is the fetcher's responsibility (source-specific logic)
    print("Pass 1: Fetching search listings...")
    try:
        listings = await fetcher.fetch_search(query, city, max_pages)
    except ValueError as e:
        raise click.ClickException(str(e))

    if not listings:
        raise click.ClickException("No listings found. Try a different model or city.")

    print(f"  Total listings found: {len(listings)}")

    for listing in listings:
        store.upsert(listing)

    # --- Pass 2: enrich with details ---
    listing_ids = [l.listing_id for l in listings]

    if no_cache:
        to_enrich = listings
    else:
        incomplete_ids = set(store.get_incomplete_ids(listing_ids))
        to_enrich = [l for l in listings if l.listing_id in incomplete_ids]

    if to_enrich:
        print(f"\nPass 2: Fetching details for {len(to_enrich)} listings...")
        enriched = await fetcher.fetch_details(to_enrich)
        for listing in enriched:
            store.upsert(listing)
    else:
        print("\nPass 2: All listings already cached, skipping detail fetch.")

    await fetcher.close()

    # --- Load full data from cache ---
    full_listings = store.get_all(listing_ids)
    print(f"\nLoaded {len(full_listings)} listings from cache.")

    # --- Analysis ---
    print("Computing KPIs...")
    kpis = compute_kpis(full_listings)

    print("Scoring listings...")
    scored = score_listings(full_listings)

    # --- Report ---
    generate_report(
        query=query,
        city=city,
        kpis=kpis,
        scored=scored,
        output_path=output_path,
    )
