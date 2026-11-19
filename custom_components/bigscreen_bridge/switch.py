"""LedFx playing or paused, through the bridge."""

from homeassistant.components.switch import SwitchEntity

from .entity import BridgeEntity, light_sections


class LedFxPlaying(BridgeEntity, SwitchEntity):
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator):
        super().__init__(coordinator, "ledfx_playing", "LedFx")

    @property
    def available(self):
        return super().available and bool(self.lights("ledfx").get("available"))

    @property
    def is_on(self):
        return not self.lights("ledfx").get("paused")

    async def async_turn_on(self, **kwargs):
        await self.coordinator.command("ledfx_pause", paused=False)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command("ledfx_pause", paused=True)


def entities(coordinator):
    return [LedFxPlaying(coordinator)] if "ledfx" in light_sections(coordinator) else []


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(entities(entry.runtime_data))
