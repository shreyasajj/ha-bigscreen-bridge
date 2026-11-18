"""LedFx scenes, activated through the bridge."""
from homeassistant.components.scene import Scene

from .entity import BridgeEntity, light_sections


class LedFxScene(BridgeEntity, Scene):
    def __init__(self, coordinator, scene):
        super().__init__(coordinator, f"ledfx_scene_{scene['id']}", f"LedFx {scene['name']}")
        self.scene_id = scene["id"]

    @property
    def available(self):
        ledfx = self.lights("ledfx")
        return super().available and bool(ledfx.get("available")) and any(
            s["id"] == self.scene_id for s in ledfx.get("scenes", []))

    async def async_activate(self, **kwargs):
        await self.coordinator.command("ledfx_scene", scene=self.scene_id, active=True)


def entities(coordinator):
    if "ledfx" not in light_sections(coordinator):
        return []
    scenes = ((coordinator.data.get("lights") or {}).get("ledfx") or {}).get("scenes") or []
    return [LedFxScene(coordinator, scene) for scene in scenes]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(entities(entry.runtime_data))
