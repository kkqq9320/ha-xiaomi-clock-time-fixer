from __future__ import annotations
import struct
import logging
from datetime import datetime

import voluptuous as vol

from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.components import bluetooth
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_UUID_TIME = 'EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6'
_UUID_TEMO = 'EBE0CCBE-7A0A-4B0C-8A1A-6FF2997DA3A6'

def get_localized_timestamp():
    """Get the current timestamp as standard UTC epoch."""
    now = dt_util.now()
    # The LYWSD02 clock adds timezone offset internally. It expects standard UTC Unix time.
    return int(now.timestamp())

def get_tz_offset():
    """Get the timezone offset dynamically from Home Assistant."""
    now = dt_util.now()
    if now.utcoffset():
        return int(now.utcoffset().total_seconds() / 3600)
    return 0

from homeassistant.exceptions import HomeAssistantError

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LYWSD02 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    @callback
    async def set_time(call: ServiceCall) -> None:
        from homeassistant.helpers import device_registry as dr
        device_registry = dr.async_get(hass)
        
        target_macs = set()
        
        # 1. Parse devices array from UI (returns device IDs)
        devices_input = call.data.get('devices', [])
        if devices_input:
            if isinstance(devices_input, str):
                devices_input = [devices_input]
            
            for device_id in devices_input:
                device = device_registry.async_get(device_id)
                if device:
                    # Connections are structured as tuples, e.g. {('bluetooth', 'A4:C1:38:62:F8:BA')}
                    for conn_type, mac in device.connections:
                        if conn_type == dr.CONNECTION_BLUETOOTH or conn_type == "bluetooth":
                            target_macs.add(mac)

        # 2. Parse custom_macs array from UI (returns raw strings)
        custom_macs_input = call.data.get('custom_macs', [])
        if custom_macs_input:
            if isinstance(custom_macs_input, str):
                import ast
                try:
                    parsed = ast.literal_eval(custom_macs_input)
                    if isinstance(parsed, list):
                        c_macs = parsed
                    else:
                        c_macs = [custom_macs_input]
                except (ValueError, SyntaxError):
                    c_macs = [m.strip() for m in custom_macs_input.split(',')]
            elif isinstance(custom_macs_input, list):
                c_macs = custom_macs_input
            else:
                c_macs = [str(custom_macs_input)]
                
            for cm in c_macs:
                if cm:
                    target_macs.add(str(cm))
                    
        # 3. Final validation and formatting
        if not target_macs:
            raise HomeAssistantError(f"No valid devices or custom MACs provided. Received: {call.data}")
            
        macs = [str(m).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip().upper() for m in target_macs if m]

        tz_offset = call.data.get('tz_offset')
        if tz_offset is None:
            tz_offset = get_tz_offset()
        else:
            tz_offset = int(tz_offset)

        # For the LYWSD02, negative timezone offsets (e.g. -9) are handled as signed 8-bit integers by struct.pack('b')
        # struct.pack('Ib', timestamp, tz_offset) will pack it correctly if it's within -128 to 127.

        timestamp = call.data.get('timestamp')
        if timestamp is None:
            timestamp = get_localized_timestamp()
        else:
            timestamp = int(timestamp)

        data = struct.pack('<Ib', timestamp, tz_offset) # Use little-endian for the timestamp

        temo_set = False
        ckmo_set = False
        # Also clean array syntax just in case they passed `["c"]` from UI
        temo = str(call.data.get('temp_mode', '') or "x").replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip().upper()
        if temo in ['C', 'F']:
            data_temp_mode = struct.pack('B', (0x01 if temo == 'F' else 0xFF))
            temo_set = True

        ckmo = call.data.get('clock_mode')
        try:
            if ckmo is not None:
                ckmo = int(ckmo)
                if ckmo in [12, 24]:
                    data_clock_mode = struct.pack('IHB', 0, 0, 0xAA if ckmo == 12 else 0x00)
                    ckmo_set = True
        except ValueError:
            pass

        tout = int(call.data.get('timeout', 60))
        
        timestamp = call.data.get('timestamp')
        if timestamp is None:
            timestamp = get_localized_timestamp()
        else:
            timestamp = int(timestamp)

        data = struct.pack('<Ib', timestamp, tz_offset) # Use little-endian for the timestamp

        errors = []
        successes = 0

        for mac in macs:
            _LOGGER.info(f"Attempting to update time on '{mac}' via ESP proxy / BT adapter.")
            ble_device = bluetooth.async_ble_device_from_address(
                hass,
                mac,
                connectable=True
            )

            if not ble_device:
                err_msg = f"Could not find '{mac}'. Make sure it's in range of an HA Bluetooth adapter or ESPHome Bluetooth Proxy."
                _LOGGER.error(err_msg)
                errors.append(err_msg)
                continue

            # Safe connection for HA/ESPHome Proxy using reliable connection wrapper
            client = await establish_connection(
                client_class=BleakClientWithServiceCache,
                device=ble_device,
                name=mac,
                disconnected_callback=None,
                max_attempts=3
            )

            if not client:
                err_msg = f"Failed to connect to device {mac} (Timeout or rejection)"
                _LOGGER.error(err_msg)
                errors.append(err_msg)
                continue

            try:
                await client.write_gatt_char(_UUID_TIME, data)
                if temo_set:
                    await client.write_gatt_char(_UUID_TEMO, data_temp_mode)
                if ckmo_set:
                    await client.write_gatt_char(_UUID_TIME, data_clock_mode)

                _LOGGER.info(f"Done - refreshed time on '{mac}' to '{timestamp}' with offset of '{tz_offset}' hours.")
                successes += 1
            except Exception as e:
                err_msg = f"Error communicating with {mac}: {e}"
                _LOGGER.error(err_msg)
                errors.append(err_msg)
            finally:
                await client.disconnect()

        # If we failed completely or partially, raise an exception so the UI shows failure
        if errors and successes == 0:
            raise HomeAssistantError(f"Failed to update all devices. Errors: {'; '.join(errors)}")
        elif errors:
            raise HomeAssistantError(f"Updated {successes} devices but failed on others. Errors: {'; '.join(errors)}")

    # Register the action/service
    hass.services.async_register(DOMAIN, 'set_time', set_time)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload LYWSD02 config entry."""
    hass.services.async_remove(DOMAIN, 'set_time')
    return True
