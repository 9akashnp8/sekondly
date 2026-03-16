import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from analysis.kpis import MarketKPIs
from analysis.scorer import ScoredListing

TEMPLATES_DIR = Path(__file__).parent / "templates"


def generate_report(
    query: str,
    city: str,
    kpis: MarketKPIs,
    scored: list[ScoredListing],
    output_path: Path,
) -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    env.filters["inr"] = _fmt_inr
    template = env.get_template("report.html")

    top_deals = [s for s in scored if s.verdict == "Great Deal"][:10]

    all_listings_json = json.dumps([
        {
            "listing_id": s.listing.listing_id,
            "title": s.listing.title,
            "url": s.listing.url,
            "image_url": s.listing.image_url,
            "price": s.listing.price,
            "year": s.listing.year,
            "km_driven": s.listing.km_driven,
            "fuel_type": s.listing.fuel_type,
            "transmission": s.listing.transmission,
            "owners": s.listing.owners,
            "variant": s.listing.variant,
            "location": s.listing.location,
            "posted_date": s.listing.posted_date.isoformat() if s.listing.posted_date else None,
            "score": s.score,
            "verdict": s.verdict,
            "reasons": s.reasons,
        }
        for s in scored
    ])

    html = template.render(
        query=query,
        city=city,
        kpis=kpis,
        top_deals=top_deals,
        all_listings_json=all_listings_json,
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"\nReport saved to: {output_path.resolve()}")


def _fmt_inr(value: int) -> str:
    """Format integer as Indian Rupee string, e.g. 1575000 → ₹15,75,000"""
    if value is None:
        return "N/A"
    s = str(int(value))
    if len(s) <= 3:
        return f"₹{s}"
    # Indian numbering: last 3 digits, then groups of 2
    last3 = s[-3:]
    rest = s[:-3]
    groups = []
    while len(rest) > 2:
        groups.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.append(rest)
    groups.reverse()
    return "₹" + ",".join(groups) + "," + last3
