"""Push updates with periodic reconnect and identity verification."""
from datetime import timedelta

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import BridgeAuthError, BridgeClient, BridgeClientError
from .const import DOMAIN


class BridgeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        import logging
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=15))
        self.entry = entry
        self.closing = False
        self.client = BridgeClient(async_get_clientsession(hass), entry.data["url"], entry.data["token"],
                                   self.async_set_updated_data, self._disconnected)

    def _disconnected(self):
        if not self.closing:
            self.async_set_update_error(UpdateFailed("Bridge disconnected"))

    async def _async_update_data(self):
        try:
            if not self.client.ws or self.client.ws.closed:
                await self.client.close()
                self.client.on_disconnect = self._disconnected
                data = await self.client.connect()
                if data["device_id"] != self.entry.unique_id:
                    await self.client.close()
                    raise UpdateFailed("Device identity changed; configure this bridge separately")
                return data
            return await self.client.command("get_state")
        except BridgeAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except (BridgeClientError, aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc

    async def command(self, command, **kwargs):
        try:
            return await self.client.command(command, **kwargs)
        except (BridgeClientError, aiohttp.ClientError, TimeoutError) as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def async_close(self):
        self.closing = True
        await self.client.close()
