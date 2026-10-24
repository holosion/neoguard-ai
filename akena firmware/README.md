# Current NeoGuard ST7789 firmware

Open **akena_firmware/akena_firmware.ino** in Arduino IDE. The full monitor now uses
the tested ST7789 240x280 SPI screen with sensors, RTC, RGB, buzzer and SD logging.
Wi-Fi and queued HTTPS backend syncing are enabled after offline integration checks.

See [wiring, upload and validation instructions](akena_firmware/README.md). Keep all
sibling headers with the sketch. The separate component tests are in `../firmware/`.
