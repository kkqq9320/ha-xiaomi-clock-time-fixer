# Xiaomi Clock Time Fixer for Home Assistant

![HACS Valid](https://img.shields.io/badge/HACS-Custom-orange.svg)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)



![0d9dea62454842cae2c0d818d4be3b9d](https://github.com/user-attachments/assets/e0c59538-ff41-49ef-b23e-5ddfac4acfd7)


A dedicated Custom Integration for Home Assistant to accurately fix and update the time, timezone, clock format, and temperature display settings of **Xiaomi LYWSD02** Bluetooth electronic ink clocks.

This integration solves common Bluetooth device communication errors (like the ESPHome `KeyError`) by utilizing Home Assistant's built-in `bleak_retry_connector` and safely interacting with your Bluetooth adapters or ESPHome Bluetooth Proxies.

## Features
- **Accurate Time Synchronization**: Syncs your clock flawlessly with Home Assistant's local time (or a custom timestamp).
- **Timezone Offset Support**: Corrects timezone display issues (supports standard int hour offsets like +9 for KST).
- **Bulk Updating**: Easily update settings across multiple clocks at once.
- **Home Assistant Device Support**: Choose your clock directly from a UI dropdown if it's already integrated via the `xiaomi_ble` integration.
- **Custom MAC Support**: If you use a standalone proxy or it's not registered in HA, manually input your MAC addresses.
- **Device UI Configurations (C/F, 12h/24h)**: Effortlessly swap between Celsius/Fahrenheit and 12-hour/24-hour formats through the Service GUI.

## Prerequisites
Before using this integration, ensure your Home Assistant server has Bluetooth connectivity to reach the LYWSD02 clocks.
- **ESPHome Bluetooth Proxy (Recommended / Tested):** Use an ESP32 as a Bluetooth proxy to relay communication safely. 
- **Local Bluetooth Adapter (Untested):** A direct USB/internal Bluetooth adapter connected to your Home Assistant host.

---

## Installation

### Method 1: HACS (Recommended)
1. Open Home Assistant and navigate to **HACS**.
2. Click on **Integrations**.
3. Click the three dots (⋮) in the top right corner and select **Custom repositories**.
4. Paste the URL of this repository.
5. Select category **Integration** and click **ADD**.
6. Close the modal, search for **Xiaomi LYWSD02 Time Fixer**, and install it.
7. Restart Home Assistant.

### Method 2: Manual Installation
1. Download the latest release from this repository.
2. Copy the `custom_components/xiaomi_clock_lywsd02` folder into your Home Assistant's `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Setup & Configuration

1. After restarting Home Assistant, go to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **Xiaomi Clock Time Fixer** and add it.

_Once configured, the `xiaomi_clock_lywsd02.set_time` Action becomes available._

---

## Usage (Actions)

Go to **Developer Tools** -> **Actions** and search for `xiaomi_clock_lywsd02.set_time`.

### UI Mode
The action is fully supported by the Home Assistant UI. You can seamlessly configure:
- **Xiaomi BLE Devices**: Select instances of your clock discovered by the `xiaomi_ble` integration.
- **Custom MAC Addresses**: Manually type MAC addresses for clocks outside the UI integration (e.g. `['A4:C1:38:62:F8:BA']`).
- **Timezone Offset**: Shift the time mathematically (e.g. `9`).
- **Temperature Unit**: `Celsius` / `Fahrenheit`.
- **Clock Format**: `12-hour AM/PM` / `24-hour`.

### YAML Mode Example
You can easily use this integration in your Automations or Scripts. For example, automatically update your clocks every day at 3 AM:

```yaml
alias: "Sync Xiaomi Clocks Time"
trigger:
  - platform: time
    at: "03:00:00"
action:
  - action: xiaomi_clock_lywsd02.set_time
    data:
      custom_macs:
        - "A4:C1:XX:XX:XX:XX"
        - "A4:C1:XX:XX:XX:XX"
      tz_offset: 9
      temp_mode: "C"
      clock_mode: "24"
```

---

## Troubleshooting

- **Error: "Failed to connect to device" / "Could not find MAC"**
Ensure that the device is near your Home Assistant host (if using a local Bluetooth dongle) or within range of an active ESPHome Bluetooth Proxy. Wait a few seconds for an advertisement to be detected before firing the service again.
- **Error popping up in UI natively**
The integration makes use of `HomeAssistantError` logic. If an update fails, verify the device is powered on and the MAC address syntax in the setup is cleanly specified without extra characters.

## Attributions
Huge thanks to [h4/lywsd02](https://github.com/h4/lywsd02) for the original reverse-engineering of the Xiaomi LYWSD02 Bluetooth GATT specifications.
