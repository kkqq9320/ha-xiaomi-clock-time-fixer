"""BLE connection and GATT write logic for Xiaomi Clock Time Fixer."""
from __future__ import annotations

import logging

from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

_UUID_TIME = 'EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6'
_UUID_TEMO = 'EBE0CCBE-7A0A-4B0C-8A1A-6FF2997DA3A6'


async def write_time_to_device(
    hass: HomeAssistant,
    mac: str,
    data: bytes,
    data_temp_mode: bytes | None = None,
    data_clock_mode: bytes | None = None,
) -> None:
    """Connect to a BLE device and write time/settings via GATT.

    Raises HomeAssistantError if the device cannot be found or communication fails.
    """
    _LOGGER.info(f"Attempting to update time on '{mac}' via ESP proxy / BT adapter.")

    ble_device = bluetooth.async_ble_device_from_address(hass, mac, connectable=True)
    if not ble_device:
        raise HomeAssistantError(
            f"Could not find '{mac}'. Make sure it's in range of an HA Bluetooth adapter or ESPHome Bluetooth Proxy."
        )

    client = await establish_connection(
        client_class=BleakClientWithServiceCache,
        device=ble_device,
        name=mac,
        disconnected_callback=None,
        max_attempts=3,
    )
    if not client:
        raise HomeAssistantError(f"Failed to connect to device {mac} (Timeout or rejection)")

    try:
        await client.write_gatt_char(_UUID_TIME, data)
        if data_temp_mode is not None:
            await client.write_gatt_char(_UUID_TEMO, data_temp_mode)
        if data_clock_mode is not None:
            try:
                await client.write_gatt_char(_UUID_TIME, data_clock_mode)
            except Exception as e:
                # LYWSD02 (original) does not support the 7-byte clock format write.
                # Only LYWSD02MMC handles it. Log a warning and continue.
                _LOGGER.warning(
                    f"Clock format could not be set on '{mac}' (device may not support it): {e}"
                )
    finally:
        await client.disconnect()
