from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .service import handle_set_time


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi Clock Time Fixer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    async def async_set_time(call):
        await handle_set_time(hass, call)

    hass.services.async_register(DOMAIN, 'set_time', async_set_time)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Xiaomi Clock Time Fixer config entry."""
    hass.services.async_remove(DOMAIN, 'set_time')
    return True
