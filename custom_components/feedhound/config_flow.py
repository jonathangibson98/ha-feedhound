"""Config flow + options flow for Feedhound (the UI side)."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import fetch_feed
from .const import (
    COMMON_FIELDS,
    CONF_DATE_FORMAT,
    CONF_EXCLUSIONS,
    CONF_FEED_URL,
    CONF_INCLUSIONS,
    CONF_LOCAL_TIME,
    CONF_REMOVE_SUMMARY_IMG,
    CONF_SHOW_TOPN,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_TOPN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _field_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=COMMON_FIELDS,
            multiple=True,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _schema(values: dict[str, Any]) -> vol.Schema:
    """Build the form. `values` pre-fills it (existing settings or last attempt)."""
    topn = values.get(CONF_SHOW_TOPN)
    topn_suggest = None if topn in (None, "", DEFAULT_TOPN) else topn

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, description={"suggested_value": values.get(CONF_NAME)}
            ): TextSelector(),
            vol.Required(
                CONF_FEED_URL, description={"suggested_value": values.get(CONF_FEED_URL)}
            ): TextSelector(),
            vol.Required(
                CONF_DATE_FORMAT,
                default=values.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT),
            ): TextSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_MINUTES),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=10080,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_SHOW_TOPN, description={"suggested_value": topn_suggest}
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=DEFAULT_TOPN, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_LOCAL_TIME, default=values.get(CONF_LOCAL_TIME, False)
            ): BooleanSelector(),
            vol.Required(
                CONF_REMOVE_SUMMARY_IMG,
                default=values.get(CONF_REMOVE_SUMMARY_IMG, False),
            ): BooleanSelector(),
            vol.Optional(
                CONF_INCLUSIONS,
                description={"suggested_value": values.get(CONF_INCLUSIONS, [])},
            ): _field_selector(),
            vol.Optional(
                CONF_EXCLUSIONS,
                description={"suggested_value": values.get(CONF_EXCLUSIONS, [])},
            ): _field_selector(),
        }
    )


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Clean up form output so the stored config is always complete and typed."""
    topn = user_input.get(CONF_SHOW_TOPN)
    return {
        CONF_NAME: user_input[CONF_NAME].strip(),
        CONF_FEED_URL: user_input[CONF_FEED_URL].strip(),
        CONF_DATE_FORMAT: user_input.get(CONF_DATE_FORMAT) or DEFAULT_DATE_FORMAT,
        CONF_SCAN_INTERVAL: int(user_input.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_MINUTES),
        CONF_SHOW_TOPN: int(topn) if topn else DEFAULT_TOPN,
        CONF_LOCAL_TIME: bool(user_input.get(CONF_LOCAL_TIME, False)),
        CONF_REMOVE_SUMMARY_IMG: bool(user_input.get(CONF_REMOVE_SUMMARY_IMG, False)),
        CONF_INCLUSIONS: [s.strip() for s in user_input.get(CONF_INCLUSIONS, []) if s.strip()],
        CONF_EXCLUSIONS: [s.strip() for s in user_input.get(CONF_EXCLUSIONS, []) if s.strip()],
    }


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Try the feed. Returns an error key, or None if it works."""
    try:
        parsed = await hass.async_add_executor_job(fetch_feed, data[CONF_FEED_URL])
    except requests.RequestException:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error while testing feed %s", data[CONF_FEED_URL])
        return "unknown"
    if not parsed.entries:
        return "invalid_feed"
    return None


class FeedhoundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a feed from the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize(user_input)
            if error := await _validate(self.hass, data):
                errors["base"] = error
            else:
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FeedhoundOptionsFlow()


class FeedhoundOptionsFlow(OptionsFlow):
    """Edit an existing UI feed (the cog/Configure button)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize(user_input)
            if error := await _validate(self.hass, data):
                errors["base"] = error
            else:
                if data[CONF_NAME] != self.config_entry.title:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, title=data[CONF_NAME]
                    )
                return self.async_create_entry(title="", data=data)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current),
            errors=errors,
        )
