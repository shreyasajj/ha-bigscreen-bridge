"""LedFx virtuals and HyperHDR instances as lights, controlled through the bridge."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError

from .entity import BridgeEntity, light_sections

VIDEO = "Video"   # HyperHDR: back to the captured video


def _level(kwargs):
    return round(kwargs[ATTR_BRIGHTNESS] / 255, 3) if ATTR_BRIGHTNESS in kwargs else None


class LedFxLight(BridgeEntity, LightEntity):
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_icon = "mdi:led-strip-variant"

    def __init__(self, coordinator, virtual):
        super().__init__(coordinator, f"ledfx_{virtual['id']}", f"LedFx {virtual['name']}")
        self.virtual_id = virtual["id"]

    @property
    def _virtual(self):
        return next((v for v in self.lights("ledfx").get("virtuals", []) if v["id"] == self.virtual_id), None)

    @property
    def available(self):
        return super().available and bool(self.lights("ledfx").get("available")) and self._virtual is not None

    @property
    def is_on(self):
        return bool((self._virtual or {}).get("active"))

    @property
    def brightness(self):
        level = (self._virtual or {}).get("brightness")
        return None if level is None else round(level * 255)

    @property
    def rgb_color(self):
        color = (self._virtual or {}).get("color")
        return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) if color else None

    @property
    def effect(self):
        return (self._virtual or {}).get("effect_name")

    @property
    def effect_list(self):
        return [e["name"] for e in self.lights("ledfx").get("effects", [])]

    async def async_turn_on(self, **kwargs):
        request = {"virtual": self.virtual_id, "on": True}
        if ATTR_EFFECT in kwargs:
            kind = next((e["type"] for e in self.lights("ledfx").get("effects", []) if e["name"] == kwargs[ATTR_EFFECT]),
                        None)
            if kind is None:
                raise HomeAssistantError("Unknown LedFx effect")
            request["effect"] = kind
        if (level := _level(kwargs)) is not None:
            request["brightness"] = level
        if ATTR_RGB_COLOR in kwargs:
            request["color"] = "#{:02x}{:02x}{:02x}".format(*kwargs[ATTR_RGB_COLOR])
        await self.coordinator.command("ledfx_light", **request)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command("ledfx_light", virtual=self.virtual_id, on=False)


class HyperHdrLight(BridgeEntity, LightEntity):
    """One HyperHDR instance: on means running. Colour and effects override the video until `Video`."""
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_assumed_state = True
    _attr_icon = "mdi:television-ambient-light"

    def __init__(self, coordinator, instance):
        super().__init__(coordinator, f"hyperhdr_{instance['id']}", f"HyperHDR {instance['name']}")
        self.instance_id = instance["id"]

    @property
    def _instance(self):
        return next((i for i in self.lights("hyperhdr").get("instances", []) if i["id"] == self.instance_id), None)

    @property
    def available(self):
        return super().available and bool(self.lights("hyperhdr").get("available")) and self._instance is not None

    @property
    def is_on(self):
        return bool((self._instance or {}).get("running"))

    @property
    def effect_list(self):
        return [VIDEO, *self.lights("hyperhdr").get("effects", [])]

    async def async_turn_on(self, **kwargs):
        request = {"instance": self.instance_id, "on": True}
        if ATTR_RGB_COLOR in kwargs:
            request["color"] = list(kwargs[ATTR_RGB_COLOR])
        if ATTR_EFFECT in kwargs:
            request["effect"] = kwargs[ATTR_EFFECT]
        if (level := _level(kwargs)) is not None:
            request["brightness"] = level
        await self.coordinator.command("hyperhdr_light", **request)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command("hyperhdr_light", instance=self.instance_id, on=False)


def entities(coordinator):
    lights = coordinator.data.get("lights") or {}
    sections = light_sections(coordinator)
    found = []
    if "ledfx" in sections:
        found += [LedFxLight(coordinator, v) for v in (lights["ledfx"].get("virtuals") or [])]
    if "hyperhdr" in sections:
        found += [HyperHdrLight(coordinator, i) for i in (lights["hyperhdr"].get("instances") or [])]
    return found


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(entities(entry.runtime_data))
