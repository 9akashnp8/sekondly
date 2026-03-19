from abc import ABC, abstractmethod

from data.schema import Listing


class BaseFetcher(ABC):
    needs_browser: bool = False  # Playwright fetchers override to True

    @abstractmethod
    async def fetch_search(self, query: str, city: str, max_pages: int) -> list[Listing]: ...

    @abstractmethod
    async def fetch_details(self, listings: list[Listing]) -> list[Listing]: ...

    async def close(self) -> None:
        """Optional resource cleanup (e.g. close aiohttp session)."""
        pass


class BaseSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def fetchers(self) -> dict[str, type[BaseFetcher]]: ...

    def get_fetcher(self, name: str, **kwargs) -> BaseFetcher:
        cls = self.fetchers.get(name)
        if cls is None:
            available = ", ".join(self.fetchers.keys())
            raise ValueError(
                f"Unknown fetcher {name!r} for source {self.name!r}. "
                f"Available: {available}"
            )
        return cls(**kwargs)
