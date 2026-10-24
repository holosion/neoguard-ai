# RGB LED and SD-card diagnostic

Offline ESP32-S3 test with status on the already working ST7789 240x280 screen.
It uses the same wiring. It does not run the temperature/oximeter tests or use Wi-Fi.
Uploading replaces the board's current diagnostic; all previous source sketches remain.

| Connection | GPIO / supply |
|---|---|
| RGB red | GPIO16 through its own 330-ohm resistor |
| RGB green | GPIO17 through its own 330-ohm resistor |
| RGB blue | GPIO18 through its own 330-ohm resistor |
| RGB common cathode | GND |
| SD CS | GPIO21 |
| SD SCK / CLK | GPIO40 |
| SD MOSI / DI | GPIO41 |
| SD MISO / DO | GPIO42 |
| SD VCC | Actual breakout's rated supply, selected by JP2 if using the carrier |
| SD GND | Common GND |
| ST7789 | Existing RST8, DC9, CS10, MOSI11, SCK12 wiring |

Use GPIO labels, not physical header positions. Disconnect power before changing
wiring or removing/inserting the SD card. The SD supply depends on the breakout;
do not assume every module uses the same VCC. Its signals must stay compatible with
3.3V ESP32 logic. Carrier JP2 pins1-2 selects 3.3V; pins2-3 selects 5V. Use one shunt.
For a verified common-anode RGB LED, set COMMON_ANODE=true and common to 3.3V.

## Test behaviour

RGB cycles RED, GREEN, BLUE, WHITE, OFF, pausing between colours. Match the external
LED's colour to the screen/serial label. Software cannot confirm emitted light;
an observed mismatch identifies channel order, polarity, wiring or LED issues.

At startup, the SD test mounts at 1 MHz with formatting explicitly disabled. It
selects an unused /ngrtestNNN.tmp filename, writes 512 pattern bytes, closes/reopens,
reads and compares, appends 128 bytes, closes/reopens, verifies all 640 bytes, then
deletes its own test file and checks removal. A failed file is retained for inspection.
Existing files are not listed, opened for writing, deleted or overwritten. This is
a small functional test, not a full-card capacity/endurance or power-loss test.

SD PASS means the most recent test completed; it is not continuous card monitoring.
Use a known readable card (FAT32 is the project's established setup). If mounting
fails, check the inserted card, supply, shared ground and four signal wires. The
sketch never formats the card. Correct wiring/power with power off, then retry SD.

## Arduino IDE

Open rgb_sd_check.ino. Libraries: Adafruit GFX Library and Adafruit ST7735 and ST7789
Library, with their dependencies. Use SPI/SD from the ESP32 board package. Select
ESP32S3 Dev Module, actual flash/PSRAM settings and correct port; enable USB CDC On
Boot for native USB Serial Monitor. Serial baud is 115200, newline enabled.

Commands: CYCLE (or RGB), RED, GREEN, BLUE, WHITE, OFF, SD, STATUS, HELP.
Manual colours stay on until another colour/CYCLE/OFF command. SD repeats the test
with a fresh mount. No buzzer is used; the existing active-high control is held low.
