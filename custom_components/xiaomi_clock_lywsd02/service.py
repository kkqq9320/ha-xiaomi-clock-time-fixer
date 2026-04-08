"""Service handler for Xiaomi Clock Time Fixer."""
from __future__ import annotations

import ast
import logging
import struct

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .ble_client import write_time_to_device
from .helpers import get_localized_timestamp, get_tz_offset

_LOGGER = logging.getLogger(__name__)


def _resolve_macs(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Extract target MAC addresses from service call data."""
    device_registry = dr.async_get(hass)
    target_macs: set[str] = set()

    devices_input = call.data.get('devices', [])
    if isinstance(devices_input, str):
        devices_input = [devices_input]
    for device_id in devices_input:
        device = device_registry.async_get(device_id)
        if device:
            for conn_type, mac in device.connections:
                if conn_type in (dr.CONNECTION_BLUETOOTH, "bluetooth"):
                    target_macs.add(mac)

    custom_macs_input = call.data.get('custom_macs', [])
    if isinstance(custom_macs_input, str):
        try:
            parsed = ast.literal_eval(custom_macs_input)
            c_macs = parsed if isinstance(parsed, list) else [custom_macs_input]
        except (ValueError, SyntaxError):
            c_macs = [m.strip() for m in custom_macs_input.split(',')]
    elif isinstance(custom_macs_input, list):
        c_macs = custom_macs_input
    else:
        c_macs = [str(custom_macs_input)]

    for cm in c_macs:
        if cm:
            target_macs.add(str(cm))

    return target_macs


def _build_payloads(call: ServiceCall, timestamp: int, tz_offset: int):
    """Build GATT byte payloads from service call data."""
    data = struct.pack('<Ib', timestamp, tz_offset)

    data_temp_mode = None
    temo = str(call.data.get('temp_mode', '') or "x").replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip().upper()
    if temo in ('C', 'F'):
        data_temp_mode = struct.pack('B', 0x01 if temo == 'F' else 0xFF)

    data_clock_mode = None
    ckmo = call.data.get('clock_mode')
    try:
        if ckmo is not None:
            ckmo = int(ckmo)
            if ckmo in (12, 24):
                data_clock_mode = struct.pack('IHB', 0, 0, 0xAA if ckmo == 12 else 0x00)
    except ValueError:
        pass

    return data, data_temp_mode, data_clock_mode


async def handle_set_time(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_time service call."""
    target_macs = _resolve_macs(hass, call)
    if not target_macs:
        raise HomeAssistantError(f"No valid devices or custom MACs provided. Received: {call.data}")

    macs = [
        str(m).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip().upper()
        for m in target_macs if m
    ]

    tz_offset = call.data.get('tz_offset')
    tz_offset = get_tz_offset() if tz_offset is None else int(tz_offset)

    timestamp = call.data.get('timestamp')
    timestamp = get_localized_timestamp() if timestamp is None else int(timestamp)

    data, data_temp_mode, data_clock_mode = _build_payloads(call, timestamp, tz_offset)

    errors = []
    successes = 0

    for mac in macs:
        try:
            await write_time_to_device(hass, mac, data, data_temp_mode, data_clock_mode)
            _LOGGER.info(f"Done - refreshed time on '{mac}' to '{timestamp}' with offset of '{tz_offset}' hours.")
            successes += 1
        except HomeAssistantError as e:
            _LOGGER.error(str(e))
            errors.append(str(e))
        except Exception as e:
            err_msg = f"Error communicating with {mac}: {e}"
            _LOGGER.error(err_msg)
            errors.append(err_msg)

    if errors and successes == 0:
        raise HomeAssistantError(f"Failed to update all devices. Errors: {'; '.join(errors)}")
    elif errors:
        raise HomeAssistantError(f"Updated {successes} devices but failed on others. Errors: {'; '.join(errors)}")
