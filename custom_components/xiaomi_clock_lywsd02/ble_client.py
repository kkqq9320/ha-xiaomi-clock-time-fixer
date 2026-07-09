"""BLE connection and GATT write logic for Xiaomi Clock Time Fixer."""
from __future__ import annotations

import asyncio
import logging

from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_UUID_TIME = 'EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6'
_UUID_TEMO = 'EBE0CCBE-7A0A-4B0C-8A1A-6FF2997DA3A6'


async def _async_get_ble_device(hass: HomeAssistant, mac: str, timeout: float):
    """Resolve a connectable BLE device, waiting for a fresh advertisement if needed."""
    ble_device = bluetooth.async_ble_device_from_address(hass, mac, connectable=True)
    if ble_device:
        return ble_device

    process_advertisements = getattr(bluetooth, "async_process_advertisements", None)
    if process_advertisements is None:
        return None

    try:
        service_info = await process_advertisements(
            hass,
            lambda info: info.address.upper() == mac.upper(),
            {"address": mac, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
            timeout,
        )
    except asyncio.TimeoutError:
        return None

    return bluetooth.async_ble_device_from_address(hass, mac, connectable=True) or getattr(
        service_info, "device", None
    )


async def write_time_to_device(
    hass: HomeAssistant,
    mac: str,
    data: bytes,
    data_temp_mode: bytes | None = None,
    data_clock_mode: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """Connect to a BLE device and write time/settings via GATT.

    Raises HomeAssistantError if the device cannot be found or communication fails.
    """
    _LOGGER.info(f"Attempting to update time on '{mac}' via ESP proxy / BT adapter.")

    ble_device = await _async_get_ble_device(hass, mac, timeout)
    if not ble_device:
        raise HomeAssistantError(
            f"Could not find '{mac}' within {timeout:g} seconds. Make sure it's in range of an HA Bluetooth adapter or ESPHome Bluetooth Proxy."
        )

    client = None
    try:
        async with asyncio.timeout(timeout):
            client = await establish_connection(
                client_class=BleakClientWithServiceCache,
                device=ble_device,
                name=mac,
                disconnected_callback=None,
                max_attempts=3,
            )
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
    except TimeoutError as err:
        raise HomeAssistantError(
            f"Timed out after {timeout:g} seconds while communicating with {mac}"
        ) from err
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            f"Error communicating with {mac}: {err}"
        ) from err
    finally:
        if client is not None:
            await client.disconnect()
