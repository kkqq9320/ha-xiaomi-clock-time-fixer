"""Timeout behavior tests for the Xiaomi clock integration."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.xiaomi_clock_lywsd02"


class HomeAssistantError(Exception):
    """Test double for Home Assistant errors."""


class ServiceValidationError(HomeAssistantError):
    """Test double for Home Assistant service validation errors."""


class HomeAssistant:
    """Test double for HomeAssistant."""


class ServiceCall:
    """Minimal service call double."""

    def __init__(self, data: dict):
        self.data = data


class FakeRegistry:
    """Device registry double with no registered devices."""

    def async_get(self, device_id: str):
        return None


class FakeClient:
    """Connected BLE client double."""

    def __init__(self):
        self.writes: list[tuple[str, bytes]] = []
        self.disconnected = False

    async def write_gatt_char(self, uuid: str, data: bytes) -> None:
        self.writes.append((uuid, data))

    async def disconnect(self) -> None:
        self.disconnected = True


def install_homeassistant_stubs() -> None:
    """Install the Home Assistant and BLE modules used by the integration."""
    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ServiceValidationError = ServiceValidationError

    util = types.ModuleType("homeassistant.util")
    dt_util = types.ModuleType("homeassistant.util.dt")
    util.dt = dt_util

    helpers = types.ModuleType("homeassistant.helpers")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.CONNECTION_BLUETOOTH = "bluetooth"
    device_registry.async_get = lambda hass: FakeRegistry()
    helpers.device_registry = device_registry

    components = types.ModuleType("homeassistant.components")
    bluetooth = types.ModuleType("homeassistant.components.bluetooth")
    bluetooth.BluetoothScanningMode = types.SimpleNamespace(ACTIVE="active")
    components.bluetooth = bluetooth

    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.exceptions": exceptions,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt_util,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.device_registry": device_registry,
            "homeassistant.components": components,
            "homeassistant.components.bluetooth": bluetooth,
        }
    )

    bleak_retry_connector = types.ModuleType("bleak_retry_connector")
    bleak_retry_connector.BleakClientWithServiceCache = object

    async def establish_connection(*args, **kwargs):
        return FakeClient()

    bleak_retry_connector.establish_connection = establish_connection
    sys.modules["bleak_retry_connector"] = bleak_retry_connector


def import_integration_module(module_name: str):
    """Import an integration module without executing its package __init__."""
    install_homeassistant_stubs()
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))

    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "xiaomi_clock_lywsd02")]
    sys.modules[PACKAGE] = package

    for loaded_name in list(sys.modules):
        if loaded_name.startswith(f"{PACKAGE}."):
            del sys.modules[loaded_name]

    return importlib.import_module(f"{PACKAGE}.{module_name}")


class TimeoutServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_passes_timeout_to_ble_writer(self) -> None:
        service = import_integration_module("service")
        calls = []

        async def fake_write_time_to_device(
            hass,
            mac,
            data,
            data_temp_mode=None,
            data_clock_mode=None,
            timeout=60,
        ):
            calls.append((mac, data, data_temp_mode, data_clock_mode, timeout))

        service.write_time_to_device = fake_write_time_to_device
        service.get_tz_offset = lambda: 9
        service.get_localized_timestamp = lambda: 1_700_000_000

        await service.handle_set_time(
            HomeAssistant(),
            ServiceCall({"custom_macs": ["AA:BB:CC:DD:EE:FF"], "timeout": 42}),
        )

        self.assertEqual(calls[0][0], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(calls[0][4], 42)


class BleClientTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_writer_waits_for_advertisement_using_timeout_when_device_missing(
        self,
    ) -> None:
        ble_client = import_integration_module("ble_client")
        bluetooth = sys.modules["homeassistant.components.bluetooth"]
        lookup_results = [None, types.SimpleNamespace(address="AA:BB:CC:DD:EE:FF")]
        advertisement_calls = []

        def fake_ble_device_from_address(hass, mac, connectable=True):
            return lookup_results.pop(0)

        async def fake_process_advertisements(
            hass,
            predicate,
            matcher,
            mode,
            timeout,
        ):
            advertisement_calls.append((matcher, mode, timeout))
            return types.SimpleNamespace(address="AA:BB:CC:DD:EE:FF")

        bluetooth.async_ble_device_from_address = fake_ble_device_from_address
        bluetooth.async_process_advertisements = fake_process_advertisements

        await ble_client.write_time_to_device(
            HomeAssistant(),
            "AA:BB:CC:DD:EE:FF",
            b"time",
            timeout=17,
        )

        self.assertEqual(advertisement_calls[0][0], {"address": "AA:BB:CC:DD:EE:FF", "connectable": True})
        self.assertEqual(advertisement_calls[0][1], "active")
        self.assertEqual(advertisement_calls[0][2], 17)

    async def test_writer_enforces_timeout_around_connection(self) -> None:
        ble_client = import_integration_module("ble_client")
        bluetooth = sys.modules["homeassistant.components.bluetooth"]
        bluetooth.async_ble_device_from_address = lambda hass, mac, connectable=True: types.SimpleNamespace(address=mac)

        async def slow_establish_connection(*args, **kwargs):
            await asyncio.sleep(1)
            return FakeClient()

        ble_client.establish_connection = slow_establish_connection

        with self.assertRaises(HomeAssistantError):
            await ble_client.write_time_to_device(
                HomeAssistant(),
                "AA:BB:CC:DD:EE:FF",
                b"time",
                timeout=0.01,
            )


if __name__ == "__main__":
    unittest.main()
