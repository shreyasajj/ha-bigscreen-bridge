"""Bridge status and LED-light sensors on the TV device."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.util import dt as dt_util

from .entity import APP_NAMES, BridgeEntity, light_sections


class StatusSensor(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key, name, value, icon=None, attributes=None, **attrs):
        super().__init__(coordinator, key, name)
        self._value, self._attributes = value, attributes
        self._attr_icon = icon
        for attr, setting in attrs.items():
            setattr(self, "_attr_" + attr, setting)

    @property
    def native_value(self):
        return self._value(self)

    @property
    def extra_state_attributes(self):
        return self._attributes(self) if self._attributes else None


class LightSensor(StatusSensor):
    """Unavailable while its service is not answering."""
    _attr_entity_category = None

    def __init__(self, coordinator, section, *args, **kwargs):
        super().__init__(coordinator, *args, **kwargs)
        self.section = section

    @property
    def available(self):
        return super().available and bool(self.lights(self.section).get("available"))


def _discovery(entity):
    discovery = entity.diagnostics.get("discovery") or {}
    if not discovery:
        return None
    return "disabled" if not discovery.get("enabled") else "announced" if discovery.get("announced") else "not_announced"


def _mqtt(entity):
    mqtt = entity.diagnostics.get("mqtt") or {}
    if not mqtt:
        return None
    return "not_configured" if not mqtt.get("configured") else "online" if mqtt.get("connected") else "offline"


def _started(entity):
    value = (entity.diagnostics.get("service") or {}).get("started_at")
    return dt_util.parse_datetime(value) if value else None


def _volume(entity):
    audio = entity.coordinator.data.get("audio") or {}
    return round(audio["volume"] * 100) if audio.get("available") and audio.get("volume") is not None else None


def _warnings(entity):
    rows = entity.diagnostics.get("warnings")
    return None if rows is None else len(rows)


def _latest_warning(entity):
    rows = entity.diagnostics.get("warnings") or []
    return {"latest": rows[-1].get("message"), "latest_at": rows[-1].get("at")} if rows else {"latest": None}


def entities(coordinator):
    found = [
        StatusSensor(coordinator, "version", "Bridge version", lambda e: (e.diagnostics.get("service") or {}).get("version"),
                     icon="mdi:tag"),
        StatusSensor(coordinator, "started", "Bridge started", _started, device_class=SensorDeviceClass.TIMESTAMP),
        StatusSensor(coordinator, "clients", "Connected clients",
                     lambda e: (e.diagnostics.get("websocket") or {}).get("clients"), icon="mdi:lan-connect",
                     state_class=SensorStateClass.MEASUREMENT),
        StatusSensor(coordinator, "discovery", "Discovery", _discovery, icon="mdi:access-point-network",
                     device_class=SensorDeviceClass.ENUM, options=["announced", "not_announced", "disabled"]),
        StatusSensor(coordinator, "mqtt", "MQTT", _mqtt, icon="mdi:transit-connection-variant",
                     device_class=SensorDeviceClass.ENUM, options=["online", "offline", "not_configured"]),
        StatusSensor(coordinator, "volume", "Volume", _volume, icon="mdi:volume-high",
                     native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
        StatusSensor(coordinator, "focused_app", "Focused app",
                     lambda e: APP_NAMES.get(e.coordinator.data.get("active_app"), "Other window"),
                     icon="mdi:application"),
        StatusSensor(coordinator, "windows", "Windows", lambda e: (e.diagnostics.get("kwin") or {}).get("windows"),
                     icon="mdi:window-restore", state_class=SensorStateClass.MEASUREMENT),
        StatusSensor(coordinator, "warnings", "Warnings", _warnings, icon="mdi:alert-outline",
                     attributes=_latest_warning, state_class=SensorStateClass.MEASUREMENT),
    ]
    sections = light_sections(coordinator)
    if "ledfx" in sections:
        devices = lambda e: e.lights("ledfx").get("devices") or {}  # noqa: E731
        found.append(LightSensor(coordinator, "ledfx", "ledfx_devices", "LedFx devices online",
                                 lambda e: devices(e).get("online"), icon="mdi:led-strip-variant",
                                 attributes=lambda e: {"total": devices(e).get("total"),
                                                       "offline": devices(e).get("offline", [])},
                                 state_class=SensorStateClass.MEASUREMENT))
    if "hyperhdr" in sections:
        found.append(LightSensor(coordinator, "hyperhdr", "hyperhdr_grabber", "HyperHDR grabber",
                                 lambda e: e.lights("hyperhdr").get("grabber") or "none", icon="mdi:video-input-hdmi",
                                 attributes=lambda e: {"last_error": e.lights("hyperhdr").get("last_error")}))
    return found


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(entities(entry.runtime_data))
