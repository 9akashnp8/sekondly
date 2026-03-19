from sources.base import BaseSource
from sources.olx.fetchers.playwright import OlxPlaywrightFetcher
from sources.olx.fetchers.api import OlxApiFetcher


class OlxSource(BaseSource):
    name = "olx"

    @property
    def fetchers(self) -> dict:
        return {
            "playwright": OlxPlaywrightFetcher,
            "api": OlxApiFetcher,
        }
