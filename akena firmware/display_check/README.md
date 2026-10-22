# Blank-screen check

This temporarily replaces the monitoring firmware. Wi-Fi, sensor readings, SD logging and alarms do not run during this check. After the check, upload `../akena_firmware/akena_firmware.ino` to restore monitoring.

Open `display_check.ino` and upload with the same ESP32-S3 board settings and port used for the main firmware. Keep the same screen wiring and previously working supply voltage. Do not change power connections while powered.

Expected output: red, green, blue, then a white page with black **NEOGUARD SCREEN TEST** text and an increasing count. Serial Monitor at 115200 prints the same test version and ticks. Seeing these Serial messages confirms this test is actually running on the board.

- If colours and text appear, the display works in isolation; report that so the full-firmware interaction can be investigated.
- If it stays blank, report the screen's printed pin labels and the ESP32 pin connected to each. The photo does not show those connections clearly enough to verify. The configured signals are MOSI 11, SCK 12, CS 10, DC 9 and RST 8, matching the original supplied working sketch. The selected driver is ST7789, 240x280, SPI mode 0.

This test uses a slower 1 MHz transfer rate and does not start the SD SPI bus. Its command-complete message does not prove the physical screen received data: the display connection has no readback confirmation.
