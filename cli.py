import asyncio
from datetime import datetime
from pathlib import Path

import click
from playwright.async_api import async_playwright

from orchestrator import run_pipeline
from sources import SOURCES, get_source

# Injected into every page before any scripts run.
# Removes JS signals that OLX uses to detect headless/automated browsers.
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
window.chrome = { runtime: {} };
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
  params.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : origQuery(params);
"""


@click.command()
@click.option("--model",     "-m", required=True,  help="Car model to search (e.g. 'Honda City')")
@click.option("--city",      "-c", required=True,  help="City name (e.g. 'Kochi')")
@click.option("--max-pages",       default=5,      show_default=True, help="Max search result pages to fetch")
@click.option("--output",    "-o", default=None,   help="Output HTML file path (default: auto-named)")
@click.option("--no-cache",        is_flag=True,   default=False, help="Ignore cached listing details and re-fetch")
@click.option("--headless",        is_flag=True,   default=False, help="Run browser in headless mode (Playwright only)")
@click.option("--source",    "-s", default="olx",  show_default=True,
              type=click.Choice(list(SOURCES.keys())), help="Data source to use")
@click.option("--fetcher",   "-f", default="playwright", show_default=True,
              help="Fetcher to use for the selected source (e.g. 'playwright', 'api')")
def main(
    model: str,
    city: str,
    max_pages: int,
    output: str | None,
    no_cache: bool,
    headless: bool,
    source: str,
    fetcher: str,
):
    """Sekondly — market intelligence for second-hand car listings."""
    asyncio.run(_run(model, city, max_pages, output, no_cache, headless, source, fetcher))


async def _run(
    model: str,
    city: str,
    max_pages: int,
    output: str | None,
    no_cache: bool,
    headless: bool,
    source_name: str,
    fetcher_name: str,
):
    # Resolve source
    try:
        source = get_source(source_name)
    except ValueError as e:
        raise click.ClickException(str(e))

    # Validate fetcher name
    fetcher_cls = source.fetchers.get(fetcher_name)
    if fetcher_cls is None:
        available = ", ".join(source.fetchers.keys())
        raise click.ClickException(
            f"Unknown fetcher {fetcher_name!r} for source {source_name!r}. "
            f"Available: {available}"
        )

    # Build output path
    if output:
        output_path = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = model.lower().replace(" ", "_")
        safe_city = city.lower().replace(" ", "_")
        output_path = Path(f"report_{safe_model}_{safe_city}_{ts}.html")

    # Gate browser lifecycle on whether the fetcher needs it
    if fetcher_cls.needs_browser:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=headless,
                args=[
                    "--disable-http2",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            await context.add_init_script(_STEALTH_SCRIPT)
            fetcher = source.get_fetcher(fetcher_name, context=context)
            await run_pipeline(source, fetcher, model, city, max_pages, no_cache, output_path)
            await browser.close()
    else:
        fetcher = source.get_fetcher(fetcher_name)
        await run_pipeline(source, fetcher, model, city, max_pages, no_cache, output_path)


if __name__ == "__main__":
    main()
