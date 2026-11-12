"""Feed fetching shared by the sensor and the config flow (blocking, run in executor)."""
from __future__ import annotations

import feedparser  # type: ignore[import]
import requests
from feedparser import FeedParserDict
from requests_file import FileAdapter

from .const import USER_AGENT


def fetch_feed(url: str) -> FeedParserDict:
    """Download and parse a feed. Raises requests exceptions on network errors."""
    with requests.Session() as session:
        session.mount("file://", FileAdapter())
        session.headers.update({"User-Agent": USER_AGENT})
        res = session.get(url, timeout=30)
        res.raise_for_status()
        return feedparser.parse(res.text)
