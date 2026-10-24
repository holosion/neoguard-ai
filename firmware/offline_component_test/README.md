# Offline ESP32-S3 component test

Separate diagnostic sketch; existing full firmware is preserved. Targets the earlier
ST7789 240x280 SPI screen (not a four-pin SSD1306/SH1106 OLED). No Wi-Fi or backend code.

Open offline_component_test.ino in Arduino IDE. Select ESP32S3 Dev Module, actual board
flash/PSRAM settings, and USB CDC On Boot enabled for native USB serial. Upload, then
open Serial Monitor at 115200 baud with newline enabled. Upload replaces the board's
running program. Re-upload the main firmware to restore it.

Install through Library Manager:
- Adafruit GFX Library
- Adafruit ST7735 and ST7789 Library
- Adafruit MLX90614 Library
- SparkFun MAX3010x Pulse and Proximity Sensor Library
- Rtc by Makuna

Wire/SPI/SD are supplied by the ESP32 board package. Use its bundled SD library.

## Wiring

Disconnect power when changing connections. Remove the parallel LCD connections first.
All grounds connect together; use GPIO labels, not physical header positions.

| Component | ESP32-S3 wiring |
|---|---|
| ST7789 | RST8, DC9, CS10, MOSI/SDA11, SCK/SCL12; compatible breakout VCC=3.3V, GND=GND |
| MAX30102 | SDA4, SCL5, compatible breakout supply=3.3V, GND; INT unused |
| MLX90614 | SDA4, SCL5, compatible breakout supply=3.3V, GND |
| DS1302 | CLK6, DAT7, CE/RST14, VCC3.3V, GND |
| microSD | CS21, SCK40, MOSI41, MISO42, module-rated supply, GND |
| Common-cathode RGB | R16, G17, B18 through separate 330-ohm resistors; common=GND |
| Active buzzer | GPIO15 through 1k to PN2222A base; 10k base to GND; emitter GND; collector buzzer minus; buzzer plus to rated supply |

For the buzzer, diode striped end goes to buzzer plus and other end to collector.
Verify transistor pinout; existing carrier design assumes a load of at most 20mA.
If using a passive piezo through a compatible driver, set ACTIVE_BUZZER=false.
For common-anode RGB, set COMMON_ANODE=true and connect common to 3.3V.
Never apply 5V to ESP32 signal pins or I2C pull-ups. SD supply depends on the breakout.
If the display has BL/BLK/LED, use its documented backlight supply/driver requirements;
this sketch does not drive a backlight GPIO. A bare LED backlight needs current limiting.

## Expected results

1. Screen shows red, green, blue and then a live status page. The controller cannot
   confirm visibility through SPI readback; physically check the screen.
2. RGB cycles red, green, blue, then off. Buzzer beeps briefly. Observe/listen directly.
3. I2C scan normally shows MAX30102 at 0x57 and MLX90614 at 0x5A.
4. MLX prints ambient and object/surface temperatures. This is not core temperature.
5. MAX prints fresh raw IR/red values. Compare uncovered and a stationary adult finger
   as a bench test. Detection/raw changes do not prove accurate HR or SpO2; this sketch
   deliberately does not calculate either.
6. RTC time should advance between reports. Plausible data alone does not confirm a
   connected/accurate DS1302. SET_RTC_FROM_BUILD=true sets compilation time once;
   ensure computer time is Nairobi local time, then set false and upload again.
   The CR2032 trickle charger is disabled.
7. SD creates an unused /ngtestNNN.txt file, writes, closes, reads and compares it.
   It deletes its own test file on success and retains it on failure. Existing files
   are preserved; the card is never formatted. Use FAT32 and power down before removal.

Serial commands: HELP, I2C, RGB, BUZZ, SCREEN, SD, RTC. Sensor output repeats every two
seconds. Manual colour/beep tests briefly pause acquisition and reset the pulse FIFO.
For an undetected sensor, fix wiring with power disconnected and reset the ESP32.
An SD test may be retried using SD. One missing component does not stop other tests.

This is a wiring/activity bench test, not measurement calibration or clinical validation.
Compilation does not establish physical operation. See BUILD_CHECK.txt for verification.
