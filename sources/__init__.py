from sources.olx import OlxSource

SOURCES: dict[str, "OlxSource"] = {
    "olx": OlxSource(),
}


def get_source(name: str):
    if name not in SOURCES:
        available = ", ".join(SOURCES.keys())
        raise ValueError(f"Unknown source {name!r}. Available: {available}")
    return SOURCES[name]
