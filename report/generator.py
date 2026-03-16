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
    all_listings = scored[:50]  # cap table at 50

    html = template.render(
        query=query,
        city=city,
        kpis=kpis,
        top_deals=top_deals,
        all_listings=all_listings,
        # JSON payloads for Chart.js
        chart_price_dist=json.dumps(kpis.price_distribution),
        chart_by_year=json.dumps(kpis.by_year),
        chart_by_fuel=json.dumps(kpis.by_fuel),
        chart_by_transmission=json.dumps(kpis.by_transmission),
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
