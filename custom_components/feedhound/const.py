"""Constants for Feedhound."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "feedhound"
VERSION = "1.1.2"

CONF_FEED_URL = "feed_url"
CONF_DATE_FORMAT = "date_format"
CONF_LOCAL_TIME = "local_time"
CONF_INCLUSIONS = "inclusions"
CONF_EXCLUSIONS = "exclusions"
CONF_SHOW_TOPN = "show_topn"
CONF_REMOVE_SUMMARY_IMG = "remove_summary_image"

DEFAULT_DATE_FORMAT = "%a, %b %d %I:%M %p"
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
DEFAULT_SCAN_MINUTES = 60  # UI stores the refresh interval in minutes
DEFAULT_THUMBNAIL = "https://www.home-assistant.io/images/favicon-192x192-full.png"
DEFAULT_TOPN = 9999
USER_AGENT = f"Home Assistant Feedhound Integration {VERSION}"
IMAGE_REGEX = r"<img.+?src=\"(.+?)\".+?>"

# Field names offered as suggestions in the UI (you can still type your own)
COMMON_FIELDS = [
    "title",
    "link",
    "summary",
    "description",
    "image",
    "published",
    "updated",
    "author",
    "id",
    "tags",
    "language",
]
