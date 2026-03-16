import aiohttp

OLX_LOCATION_API = "https://www.olx.in/api/locations/autocomplete"


async def resolve_location(city: str) -> tuple[str, int]:
    """
    Return (slug, id) for the best match city, e.g. ("kochi", 4058873).
    Raises ValueError if no match found.
    """
    params = {"input": city, "limit": 5, "lang": "en-IN"}
    async with aiohttp.ClientSession() as session:
        async with session.get(OLX_LOCATION_API, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

    suggestions = data.get("data", {}).get("suggestions", [])
    if not suggestions:
        raise ValueError(f"No location found for '{city}'. Try a different city name.")

    # Prefer CITY type, fall back to first result
    match = next((s for s in suggestions if s.get("type") == "CITY"), suggestions[0])
    slug = match["name"].lower().replace(" ", "-")
    return slug, match["id"]


def build_search_url(location_slug: str, location_id: int, query: str) -> str:
    """
    Build OLX search URL.
    Example: https://www.olx.in/kochi_g4058873/cars_c84/q-virtus
    """
    query_slug = query.strip().lower().replace(" ", "-")
    return f"https://www.olx.in/{location_slug}_g{location_id}/cars_c84/q-{query_slug}"
