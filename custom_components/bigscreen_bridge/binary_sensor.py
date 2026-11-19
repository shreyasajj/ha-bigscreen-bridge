"""Bridge health, the display, and whether LedFx and HyperHDR run."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import BridgeEntity, light_sections


class StatusBinary(BridgeEntity, BinarySensorEntity):
    def __init__(
        self, coordinator, key, name, value, device_class=None, category=EntityCategory.DIAGNOSTIC, needs=None
    ):
        super().__init__(coordinator, key, name)
        self._value, self._needs = value, needs
        self._attr_device_class, self._attr_entity_category = device_class, category

    @property
    def available(self):
        if self._needs and not self.lights(self._needs).get("available"):
            return False
        return super().available

    @property
    def is_on(self):
        return self._value(self)


def _health(entity):
    health = (entity.diagnostics.get("service") or {}).get("health")
    return None if health is None else health != "ok"


def _display(entity):
    return ((entity.coordinator.data.get("power") or {}).get("display") or {}).get("display_on")


def entities(coordinator):
    found = [
        StatusBinary(coordinator, "health", "Bridge health", _health, BinarySensorDeviceClass.PROBLEM),
        StatusBinary(coordinator, "display", "Display", _display, BinarySensorDeviceClass.POWER),
    ]
    sections = light_sections(coordinator)
    for section, label in (("ledfx", "LedFx"), ("hyperhdr", "HyperHDR")):
        if section in sections:
            found.append(
                StatusBinary(
                    coordinator,
                    f"{section}_service",
                    f"{label} service",
                    lambda e, s=section: e.lights(s).get("service") == "active",
                    BinarySensorDeviceClass.RUNNING,
                )
            )
    if "hyperhdr" in sections:
        found.append(
            StatusBinary(
                coordinator,
                "hyperhdr_output",
                "HyperHDR output",
                lambda e: e.lights("hyperhdr").get("output"),
                BinarySensorDeviceClass.LIGHT,
                category=None,
                needs="hyperhdr",
            )
        )
    return found


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(entities(entry.runtime_data))
