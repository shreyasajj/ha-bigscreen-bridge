"""Connect to an authenticated bridge using the UI."""
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client import BridgeAuthError, BridgeClient, BridgeClientError, validate_url
from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _found = None

    async def async_step_zeroconf(self, discovery_info):
        """A bridge announced itself; only the private token is still needed."""
        device_id = discovery_info.properties.get("device_id")
        if not device_id or discovery_info.properties.get("protocol") != "1":
            return self.async_abort(reason="not_supported")
        host = discovery_info.host
        try:
            url = validate_url(f"http://{'[' + host + ']' if ':' in host else host}:{discovery_info.port}")
        except ValueError:
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(device_id)
        # A known TV that moved to another address is simply followed.
        self._abort_if_unique_id_configured(updates={"url": url})
        self._found = {"url": url, "name": discovery_info.properties.get("name") or host}
        self.context["title_placeholders"] = {"name": self._found["name"]}
        return await self.async_step_pair()

    async def async_step_pair(self, user_input=None):
        errors = {}
        if user_input:
            client = BridgeClient(async_get_clientsession(self.hass), self._found["url"], user_input["token"])
            try:
                state = await client.connect()
                if state["device_id"] != self.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_create_entry(title=state["name"],
                                                   data={"url": self._found["url"], "token": user_input["token"]})
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except (BridgeClientError, aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
        return self.async_show_form(step_id="pair", data_schema=vol.Schema({
            vol.Required("token"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors, description_placeholders=self._found)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            client = None
            try:
                url = validate_url(user_input["url"])
                client = BridgeClient(async_get_clientsession(self.hass), url, user_input["token"])
                state = await client.connect()
                await self.async_set_unique_id(state["device_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=state["name"], data={**user_input, "url": url})
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "invalid_url"
            except (BridgeClientError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            finally:
                if client:
                    await client.close()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("url"): str,
            vol.Required("token"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors, description_placeholders={"example": "http://tv.local:8765"})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input:
            client = BridgeClient(async_get_clientsession(self.hass), entry.data["url"], user_input["token"])
            try:
                state = await client.connect()
                if state["device_id"] != entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except (BridgeClientError, aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required("token"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors)
