"""Constants for the Moonlight Voice integration."""

DOMAIN = "moonlight_voice"
CONF_URL = "url"
# Locally deployed add-ons are named `{repository}_{slug}` by Supervisor.
# The local repository identifier is `local`; Docker DNS requires hyphens.
DEFAULT_URL = "http://local-moonlight-voice:8031"
HOME_ASSISTANT_MODE = "home_assistant"
