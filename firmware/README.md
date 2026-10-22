# NeoGuard firmware

The current complete package is [akena firmware/akena_firmware](../akena%20firmware/akena_firmware/README.md): minute-long signal checks, separate pulse acquisition, red/buzzer threshold alarms, phone Wi-Fi provisioning, automatic session discovery, and SD-backed replay. Open its `akena_firmware.ino`; older sketches below remain as historical bench references.

The latest revision based on the user's confirmed working sketch is **sketch_oct12a/sketch_oct12a.ino**. It uses blue for normal sensor operation, preserves the existing sensor validity limits and display icons, improves SD diagnostics, and supports configured SD-backed Wi-Fi replay to the backend. See [its setup guide](sketch_oct12a/README.md); automatic upload requires the device/session configuration and supplied certificate on the card. The Desktop `sketch_oct12a` folder contains the same revision and a backup of the original working sketch.

Open **neoguard_system/neoguard_system.ino** in Arduino IDE for the full wired ESP32-S3 bench system. Keep its sibling **display_icons.h** in the same sketch folder.

- [Full wiring, upload, SD logging, and clock-setting guide](neoguard_system/README.md)
- [Set the RTC from current Nairobi time after upload](neoguard_system/sync_rtc.ps1)
- [Illustrative dashboard preview](neoguard_system/assets/display_preview.png)
- [Original icon assets and rebuild script](neoguard_system/assets/)
- [Initial two-sensor test](sensors_step1/README.md)

Default hardware: ESP32-S3, ST7789 240x280 SPI screen, MAX30102, MLX90614, DS1302, RGB LED, buzzer, and SPI microSD module. SD logging is enabled. This is an experimental standalone hardware prototype; it does not send readings to the web application and is not clinically validated.
