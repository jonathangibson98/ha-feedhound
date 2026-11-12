"""Feedhound sensor."""
from __future__ import annotations

import email.utils
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from dateutil import parser
from feedparser import FeedParserDict
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_UNIQUE_ID
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt

from .api import fetch_feed
from .const import (
    CONF_DATE_FORMAT,
    CONF_EXCLUSIONS,
    CONF_FEED_URL,
    CONF_INCLUSIONS,
    CONF_LOCAL_TIME,
    CONF_REMOVE_SUMMARY_IMG,
    CONF_SHOW_TOPN,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_THUMBNAIL,
    DEFAULT_TOPN,
    IMAGE_REGEX,
    VERSION,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

__version__ = VERSION

COMPONENT_REPO = "https://github.com/jonathangibson98/feedhound/"

REQUIREMENTS = ["feedparser"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FEED_URL): cv.string,
        vol.Required(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): cv.string,
        vol.Optional(CONF_LOCAL_TIME, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_TOPN, default=DEFAULT_TOPN): cv.positive_int,
        vol.Optional(CONF_REMOVE_SUMMARY_IMG, default=False): cv.boolean,
        vol.Optional(CONF_INCLUSIONS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXCLUSIONS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        # Optional: give a YAML sensor a unique_id so you can also tweak its
        # name/icon/area/entity_id from the UI.
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    },
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,  # noqa: ARG001
    config: ConfigType,
    async_add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # noqa: ARG001
) -> None:
    """Set up a Feedhound sensor from YAML (unchanged behaviour)."""
    async_add_devices(
        [
            FeedParserSensor(
                feed=config[CONF_FEED_URL],
                name=config[CONF_NAME],
                date_format=config[CONF_DATE_FORMAT],
                show_topn=config[CONF_SHOW_TOPN],
                remove_summary_image=config[CONF_REMOVE_SUMMARY_IMG],
                inclusions=config[CONF_INCLUSIONS],
                exclusions=config[CONF_EXCLUSIONS],
                scan_interval=config[CONF_SCAN_INTERVAL],
                local_time=config[CONF_LOCAL_TIME],
                unique_id=config.get(CONF_UNIQUE_ID),
            ),
        ],
        update_before_add=True,
    )


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Feedhound sensor from the UI."""
    cfg: dict[str, Any] = {**entry.data, **entry.options}
    async_add_entities(
        [
            FeedParserSensor(
                feed=cfg[CONF_FEED_URL],
                name=cfg[CONF_NAME],
                date_format=cfg.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT),
                show_topn=int(cfg.get(CONF_SHOW_TOPN, DEFAULT_TOPN)),
                remove_summary_image=cfg.get(CONF_REMOVE_SUMMARY_IMG, False),
                inclusions=list(cfg.get(CONF_INCLUSIONS, [])),
                exclusions=list(cfg.get(CONF_EXCLUSIONS, [])),
                # the UI stores the interval as whole minutes
                scan_interval=timedelta(
                    minutes=int(cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_MINUTES))
                ),
                local_time=cfg.get(CONF_LOCAL_TIME, False),
                unique_id=entry.entry_id,
                self_scheduled=True,
            ),
        ],
        # No update_before_add here: if the feed is down at boot the entity still
        # gets created and fills in on the first successful refresh.
    )


class FeedParserSensor(SensorEntity):
    """Representation of a Feedhound sensor."""

    # force update the entity since the number of feed entries does not necessarily
    # change, but we still want to update the extra_state_attributes
    _attr_force_update = True

    def __init__(
        self: FeedParserSensor,
        feed: str,
        name: str,
        date_format: str,
        show_topn: int,
        remove_summary_image: bool,
        exclusions: list[str | None],
        inclusions: list[str | None],
        scan_interval: timedelta,
        local_time: bool,
        unique_id: str | None = None,
        self_scheduled: bool = False,
    ) -> None:
        """Initialize the Feedparser sensor."""
        self._feed = feed
        self._attr_name = name
        self._attr_icon = "mdi:rss"
        self._date_format = date_format
        self._show_topn: int = show_topn
        self._remove_summary_image = remove_summary_image
        self._inclusions = inclusions
        self._exclusions = exclusions
        self._scan_interval = scan_interval
        self._local_time = local_time
        self._entries: list[dict[str, str]] = []
        self._attr_extra_state_attributes = {"entries": self._entries}
        self._attr_attribution = "Data retrieved by Feedhound"
        self._attr_unique_id = unique_id
        # YAML sensors are polled by the platform (scan_interval handled by HA).
        # UI sensors run their own timer so each feed keeps its own interval.
        self._attr_should_poll = not self_scheduled
        _LOGGER.debug("Feed %s: FeedParserSensor initialized - %s", self.name, self)

    def __repr__(self: FeedParserSensor) -> str:
        """Return the representation."""
        return (
            f'FeedParserSensor(name="{self.name}", feed="{self._feed}", '
            f"show_topn={self._show_topn}, "
            f"remove_summary_image={self._remove_summary_image}, "
            f"inclusions={self._inclusions}, "
            f"exclusions={self._exclusions}, scan_interval={self._scan_interval}, "
            f'local_time={self._local_time}, date_format="{self._date_format}")'
        )

    async def async_added_to_hass(self: FeedParserSensor) -> None:
        """Start our own refresh timer (UI sensors only)."""
        if self._attr_should_poll:
            return
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_scheduled_refresh, self._scan_interval
            )
        )
        # first refresh right away, without blocking setup
        self.hass.async_create_task(self._async_scheduled_refresh(None))

    async def _async_scheduled_refresh(self: FeedParserSensor, _now: datetime | None) -> None:
        await self.async_update_ha_state(force_refresh=True)

    def update(self: FeedParserSensor) -> None:
        """Parse the feed and update the state of the sensor."""
        _LOGGER.debug("Feed %s: Polling feed data from %s", self.name, self._feed)
        parsed_feed: FeedParserDict = fetch_feed(self._feed)

        if not parsed_feed.entries:
            self._attr_native_value = None
            _LOGGER.warning("Feed %s: No data received.", self.name)
            return

        _LOGGER.debug("Feed %s: Feed data fetched successfully", self.name)
        # set the sensor value to the amount of entries
        self._attr_native_value = (
            self._show_topn
            if len(parsed_feed.entries) > self._show_topn
            else len(parsed_feed.entries)
        )
        _LOGGER.debug(
            "Feed %s: %s entries is going to be added to the sensor",
            self.name,
            self.native_value,
        )
        self._entries.clear()  # clear the entries to avoid duplicates
        self._entries.extend(self._generate_entries(parsed_feed))
        _LOGGER.debug(
            "Feed %s: Sensor state updated - %s entries",
            self.name,
            len(self.feed_entries),
        )

    def _generate_entries(
        self: FeedParserSensor,
        parsed_feed: FeedParserDict,
    ) -> list[dict[str, str]]:
        return [
            self._generate_sensor_entry(feed_entry)
            for feed_entry in parsed_feed.entries[
                : self.native_value  # type: ignore[misc]
            ]
        ]

    def _generate_sensor_entry(
        self: FeedParserSensor,
        feed_entry: FeedParserDict,
    ) -> dict[str, str]:
        _LOGGER.debug("Feed %s: Generating sensor entry for %s", self.name, feed_entry)
        sensor_entry = {}
        for key, value in feed_entry.items():
            if (
                (self._inclusions and key not in self._inclusions)
                or ("parsed" in key)
                or (key in self._exclusions)
            ):
                continue
            if key in ["published", "updated", "created", "expired"]:
                parsed_date: datetime = self._parse_date(value)
                sensor_entry[key] = parsed_date.strftime(self._date_format)
            elif key == "image":
                sensor_entry["image"] = value.get("href")
            else:
                sensor_entry[key] = value

        if "image" in self._inclusions and "image" not in sensor_entry:
            sensor_entry["image"] = self._process_image(feed_entry)
        if (
            "link" in self._inclusions
            and "link" not in sensor_entry
            and (processed_link := self._process_link(feed_entry))
        ):
            sensor_entry["link"] = processed_link
        if self._remove_summary_image and "summary" in sensor_entry:
            sensor_entry["summary"] = re.sub(
                IMAGE_REGEX,
                "",
                sensor_entry["summary"],
            )
        _LOGGER.debug("Feed %s: Generated sensor entry: %s", self.name, sensor_entry)
        return sensor_entry

    def _parse_date(self: FeedParserSensor, date: str) -> datetime:
        try:
            parsed_time: datetime = email.utils.parsedate_to_datetime(date)
        except ValueError:
            _LOGGER.warning(
                (
                    "Feed %s: Unable to parse RFC-822 date from %s. "
                    "This could be caused by incorrect pubDate format "
                    "in the RSS feed or due to a leapp second"
                ),
                self.name,
                date,
            )
            # best effort to parse the date using dateutil
            parsed_time = parser.parse(date)

        if not parsed_time.tzinfo:
            # best effort to parse the date using dateutil
            parsed_time = parser.parse(date)
            if not parsed_time.tzinfo:
                msg = (
                    f"Feed {self.name}: Unable to parse date {date}, "
                    "caused by an incorrect date format"
                )
                raise ValueError(msg)
        if not parsed_time.tzname():
            # replace tzinfo with UTC offset if tzinfo does not contain a TZ name
            parsed_time = parsed_time.replace(
                tzinfo=timezone(parsed_time.utcoffset()),  # type: ignore[arg-type]
            )

        if self._local_time:
            parsed_time = dt.as_local(parsed_time)
        _LOGGER.debug("Feed %s: Parsed date: %s", self.name, parsed_time)
        return parsed_time

    def _process_image(self: FeedParserSensor, feed_entry: FeedParserDict) -> str:
        if feed_entry.get("enclosures"):
            images = [
                enc for enc in feed_entry["enclosures"] if enc.type.startswith("image/")
            ]
            if images:
                # pick the first image found
                return images[0]["href"]
        elif "summary" in feed_entry:
            images = re.findall(
                IMAGE_REGEX,
                feed_entry["summary"],
            )
            if images:
                # pick the first image found
                return images[0]
        _LOGGER.debug(
            "Feed %s: Image is in inclusions, but no image was found for %s",
            self.name,
            feed_entry,
        )
        return DEFAULT_THUMBNAIL  # use default image if no image found

    def _process_link(self: FeedParserSensor, feed_entry: FeedParserDict) -> str:
        """Return link from feed entry."""
        if "links" in feed_entry:
            if len(feed_entry["links"]) > 1:
                _LOGGER.debug(
                    "Feed %s: More than one link found for %s. Using the first link.",
                    self.name,
                    feed_entry,
                )
            return feed_entry["links"][0]["href"]
        return ""

    @property
    def feed_entries(self: FeedParserSensor) -> list[dict[str, str]]:
        """Return feed entries."""
        if hasattr(self, "_entries"):
            return self._entries
        return []

    @property
    def local_time(self: FeedParserSensor) -> bool:
        """Return local_time."""
        return self._local_time

    @local_time.setter
    def local_time(self: FeedParserSensor, value: bool) -> None:
        """Set local_time."""
        self._local_time = value

    @property
    def extra_state_attributes(self: FeedParserSensor) -> dict[str, list]:
        """Return entity specific state attributes."""
        return {"entries": self.feed_entries}
