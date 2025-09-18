from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN, CONF_API_KEY
from .api import MetlinkApiClient

class MetlinkExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            client = MetlinkApiClient(api_key)
            valid = await client.validate_api_key()
            await client.close()
            if valid:
                return self.async_create_entry(title="Metlink Explorer", data={CONF_API_KEY: api_key})
            else:
                errors["base"] = "invalid_api_key"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )