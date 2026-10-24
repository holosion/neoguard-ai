# NeoGuard firmware

The only current device firmware is [akena_firmware](../akena%20firmware/akena_firmware/README.md).
Open `akena firmware/akena_firmware/akena_firmware.ino` in Arduino IDE and keep its required headers beside it.

Hardware: ESP32-S3 and the tested ST7789 240x280 SPI screen. The full build combines
sensors, RTC, RGB, alarms and SD logging. Wi-Fi provisioning and queued HTTPS
syncing are enabled; NEOGUARD_ENABLE_NETWORK=0 provides an offline-only build.

`display_sensor_check/`, `rgb_sd_check/` and `offline_component_test/` are separate
component diagnostics with their own test reports. `tests/` contains host-side
measurement checks. `system_test/` is an older LCD diagnostic, not the current firmware.
