"""Constants for Predictive Climate Control."""

DOMAIN = "predictive_climate_control"

CONF_INDOOR_ENTITY = "indoor_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_MASS_ENTITY = "mass_entity"
CONF_HORIZON_HOUR = "horizon_hour"

# Minutes of each hour at which the live forecast refreshes.
REFRESH_MINUTES = (0, 15, 30, 45)
# Minute of each hour at which the frozen curve's current value is promoted.
PROMOTE_MINUTE = 1
# Minute after the horizon hour at which the nightly snapshot is taken.
SNAPSHOT_MINUTE = 2

STORAGE_VERSION = 1
