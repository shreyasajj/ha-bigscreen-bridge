"""Entities on the TV's device that read the bridge's snapshot or diagnostics."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

APP_NAMES = {
    "couchside": "Couchside",
    "stremio": "Stremio TV",
    "flimmer": "Flimmer",
    "vacuumtube": "VacuumTube",
}


class BridgeEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        device_id = coordinator.data["device_id"]
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.data["name"],
            manufacturer="KDE",
            model="Plasma Bigscreen",
        )

    @property
    def diagnostics(self):
        return self.coordinator.diagnostics or {}

    def lights(self, name):
        """`snapshot.lights.<name>`, or {} when this bridge does not report it."""
        return (self.coordinator.data.get("lights") or {}).get(name) or {}


def light_sections(coordinator):
    """Which of LedFx and HyperHDR the bridge reports (an older bridge reports neither)."""
    return set((coordinator.data.get("lights") or {}).keys()) & {"ledfx", "hyperhdr"}
