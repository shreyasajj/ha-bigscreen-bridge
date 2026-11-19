"""Settings → Devices & services → Download diagnostics: the bridge's own report, never the token."""

from homeassistant.components.diagnostics import async_redact_data


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    await coordinator.refresh_diagnostics()
    return {
        "entry": async_redact_data(dict(entry.data), {"token"}),
        "state": coordinator.data,
        "bridge_diagnostics": coordinator.diagnostics,
    }
