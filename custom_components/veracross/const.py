"""Constants for the Veracross integration."""

DOMAIN = "veracross"

CONF_SCHOOL = "school"

# subprocess tuning
DEFAULT_TIMEOUT_S = 120
BINARY_DIR_NAME = "bin"
BINARY_PREFIX = "vx_ha_cli_linux_"

# hass.data keys
DATA_MANAGER = "manager"

# signal dispatched whenever fresh grade data lands
SIGNAL_GRADES_UPDATED = "veracross_grades_updated_{entry_id}"
SIGNAL_UPDATING_STATE = "veracross_updating_state_{entry_id}"
