"""Feedhound: pull any RSS/Atom feed into a Home Assistant sensor.

Based on the MIT-licensed sensor.feedparser by Ian Richardson (@iantrich)
and Ondrej Gajdusek (@ogajduse).

Feeds can be set up two ways:
  * YAML:  sensor: - platform: feedhound  (unchanged from 1.0.0)
  * UI:    Settings -> Devices & services -> Add integration -> Feedhound
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a UI-created Feedhound feed."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Reload the feed whenever its options are edited in the UI
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a UI-created Feedhound feed."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after an options change."""
    hass.config_entries.async_schedule_reload(entry.entry_id)
