"""Setup and options flows."""
from __future__ import annotations

from dataclasses import asdict

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import model
from .const import (
    CONF_HORIZON_HOUR,
    CONF_INDOOR_ENTITY,
    CONF_MASS_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)

_TEMPERATURE = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="temperature"))
_WEATHER = selector.EntitySelector(selector.EntitySelectorConfig(domain="weather"))
_NUMBER = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any"))
_HOUR = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, min=0, max=23, step=1))


def _entity_schema(current: dict) -> dict:
    """Entity fields, prefilled from `current`. The mass entity can be left empty."""
    return {
        vol.Required(CONF_INDOOR_ENTITY,
                     description={"suggested_value": current.get(CONF_INDOOR_ENTITY)}): _TEMPERATURE,
        vol.Required(CONF_WEATHER_ENTITY,
                     description={"suggested_value": current.get(CONF_WEATHER_ENTITY)}): _WEATHER,
        vol.Optional(CONF_MASS_ENTITY,
                     description={"suggested_value": current.get(CONF_MASS_ENTITY)}): _TEMPERATURE,
    }


class PredictiveClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick the indoor sensor, the weather entity, and optionally a mass sensor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Predictive Climate Control", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema(_entity_schema({})))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PredictiveClimateOptionsFlow()


class PredictiveClimateOptionsFlow(OptionsFlow):
    """Change entities, the horizon hour, and every coefficient without a restart."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # An emptied mass entity must override the one chosen at setup.
            user_input.setdefault(CONF_MASS_ENTITY, None)
            user_input[CONF_HORIZON_HOUR] = int(user_input[CONF_HORIZON_HOUR])
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = _entity_schema(current)
        schema[vol.Required(
            CONF_HORIZON_HOUR,
            default=current.get(CONF_HORIZON_HOUR, model.DEFAULT_HORIZON_HOUR))] = _HOUR
        for name, default in asdict(model.Coefficients()).items():
            schema[vol.Required(name, default=current.get(name, default))] = _NUMBER
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
