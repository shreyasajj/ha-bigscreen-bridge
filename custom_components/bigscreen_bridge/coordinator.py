"""Push updates with periodic reconnect and identity verification."""
import time
from datetime import timedelta

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import BridgeAuthError, BridgeClient, BridgeClientError
from .const import DOMAIN

DIAGNOSTICS_INTERVAL = 30   # seconds between reads of the bridge's diagnostics


class BridgeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        import logging
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=15))
        self.entry = entry
        self.closing = False
        self.diagnostics = None          # the bridge's `diagnostics` reply; None until read or if unsupported
        self.diagnostics_at = 0.0
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
                await self.refresh_diagnostics()
                return data
            data = await self.client.command("get_state")
            if time.monotonic() - self.diagnostics_at >= DIAGNOSTICS_INTERVAL:
                await self.refresh_diagnostics()
            return data
        except BridgeAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except (BridgeClientError, aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc

    async def refresh_diagnostics(self):
        """Bridge status for the diagnostic entities; an older bridge without the command just has none."""
        self.diagnostics_at = time.monotonic()
        try:
            self.diagnostics = await self.client.command("diagnostics")
        except BridgeAuthError:
            raise
        except (BridgeClientError, aiohttp.ClientError, TimeoutError) as exc:
            if getattr(exc, "code", None) == "unsupported":
                self.diagnostics = None

    async def command(self, command, **kwargs):
        try:
            return await self.client.command(command, **kwargs)
        except (BridgeClientError, aiohttp.ClientError, TimeoutError) as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def async_close(self):
        self.closing = True
        await self.client.close()
