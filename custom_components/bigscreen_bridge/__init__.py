"""Native Bigscreen Bridge integration."""
from homeassistant.const import Platform

from .coordinator import BridgeCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.LIGHT,
             Platform.SCENE]


async def async_setup_entry(hass, entry):
    coordinator = BridgeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_close()
        raise
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_close()
        return True
    return False
