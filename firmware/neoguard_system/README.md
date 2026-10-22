# NeoGuard complete hardware bench sketch

This integrates the components present in the earlier sketches: ESP32-S3, display, MAX30102, MLX90614, DS1302, external RGB LED, buzzer, and optional SPI microSD. It runs without Wi-Fi and reports one CSV row approximately every second to Serial Monitor. It does not upload readings to the dashboard/API, assign patients, or implement clinical alarms.

## SD card logging enabled

`ENABLE_SD_LOGGING = true` is now the default. Unplug power, insert the FAT32 microSD card, and upload the updated sketch. The footer shows **SD LOGGING** and the number of rows successfully written during this boot. Records append to `/neoguard.csv`, approximately once per second, with a header created automatically for an empty file. The log includes local RTC timestamps and validity flags.

The existing SD wiring stays the same: CS=21, SCK=40, MOSI=41, MISO=42, shared GND. The blue regulator-equipped module photographed in this conversation uses its module supply input as previously wired; do not change sensor/display supplies to match it. If storage is unavailable, the rest of the device still runs and the footer shows **SD NOT READY**. There is a retry every ten seconds; unsaved readings are not buffered for later replay. To intentionally run without storage, set `ENABLE_SD_LOGGING = false`.

## Set the actual Nairobi date and time after upload

The DS1302 keeps time once set and powered by its backup battery; it has no automatic source of the current date/time. This version preserves a valid running clock and does not silently substitute compilation time for an unset RTC. The display shows **SET CLOCK VIA USB** while it is unset. No date/time is hard-coded in the firmware.

1. Upload the sketch, then **close Arduino Serial Monitor and Serial Plotter** so the helper can open the port.
2. Open PowerShell in this project and run:

   ```powershell
   .\firmware\neoguard_system\sync_rtc.ps1 -ListPorts
   .\firmware\neoguard_system\sync_rtc.ps1 -Port COM5
   ```

   Replace `COM5` with the ESP32's port shown in Arduino IDE. If exactly one serial port is available, the helper can choose it when `-Port` is omitted. If Windows blocks script execution, invoke it for this one process using `powershell -NoProfile -ExecutionPolicy Bypass -File .\firmware\neoguard_system\sync_rtc.ps1 -Port COM5`.
3. The helper waits for device startup, obtains the computer's current time converted to **Nairobi UTC+03:00**, sends it, and requires an **RTC SET OK** readback. A correct computer clock is required. Transport/readback introduces a small delay; this is not precision time synchronization or an internet time service.
4. Reopen Serial Monitor at 115200 baud if desired. Send `TIME?` with a newline to inspect the clock. The clock should continue advancing after a reset; confirm it also retains time after disconnecting USB with the backup battery fitted.

You can also send `TIME YYYY-MM-DD HH:MM:SS` in Serial Monitor, substituting the actual current Nairobi local date/time and selecting **Newline**. Input is validated for calendar dates and the supported 2020-2099 year range. Setting the clock does not rewrite existing SD rows. Until a clock is valid, CSV timestamps are blank and `rtc_valid=0`.

`SET_RTC_TIME` and `AUTO_SET_RTC_IF_INVALID` remain available as explicit compilation-time fallback settings but both default to `false`; use the helper for a current-time update without recompiling.

## Display images and layout

The default remains the wired **ST7789 240 x 280 SPI display**. The dashboard includes a heart-rate card with a heart image, SpO2 droplet image, surface-temperature card with a thermometer image, live date/time with a clock icon, ambient temperature, signal status, and SD status. Status text describes availability, not clinical health. No artificial ECG trace or simulated readings appear on the device.

All five pictograms are embedded in `display_icons.h` as 16/32-pixel monochrome bitmaps, tinted by the display code. **No images need copying to the SD card**, and the icons remain available if the card fails. The `assets/` folder contains the original SVG images, a rebuild script, and `display_preview.png`. The preview uses illustrative numbers; actual firmware values come from the sensors and RTC.

The screen updates small panels and services pulse sampling between them to reduce flicker and sampling gaps. The optional SSD1306 mode uses a compact monochrome version with heart and thermometer images.

## Build verification

The SD-enabled/icon-dashboard version compiled successfully on 19 October 2026 with Arduino ESP32 core 3.3.12, target `esp32:esp32:esp32s3:CDCOnBoot=cdc`. Program storage: 413794 bytes (31%); global RAM: 26032 bytes (7%). The clock helper passed syntax, Windows PowerShell execution, live Nairobi-time formatting, and read-only port discovery checks; all ten embedded icon bitmap sizes were verified and the preview was visually inspected. Compilation and host checks do not verify the assembled hardware; SD read/write, clock retention, serial synchronization, and sensor accuracy still require checks on the actual device.

This is a bench prototype, not a clinically validated neonatal monitor. The MLX90614 reports object/surface temperature, not core body temperature. The MAX reference algorithm and finger-contact threshold are for bench experiments, not validated neonatal measurements. Green means estimates are available, not that a baby is healthy. The buzzer sounds once at startup to test hardware.

## Confirm the display first

The previous `firmware/display_message` sketch uses a **240 x 280 ST7789 SPI TFT**. The new sketch defaults to that same display (`DISPLAY_KIND 1`). Although sometimes called an OLED informally, an ST7789 TFT uses a different driver and wiring from an OLED.

If the replacement is specifically a **128 x 64 SSD1306 I2C OLED**, set `DISPLAY_KIND` to `2` and use the separate OLED wiring below. Default address is `0x3C`; change `OLED_ADDRESS` to `0x3D` if the scan finds that address. SH1106, SSD1309, SPI OLEDs, and other resolutions need their own configuration; do not select SSD1306 just because the screen has four pins.

## Connections

Switch off and unplug power while wiring. These numbers are **GPIO labels on the ESP32-S3**, not header positions. All modules must share GND. Use breakout boards compatible with 3.3 V logic; ESP32-S3 inputs must not receive 5 V. Confirm module power requirements from its markings/datasheet before connecting it. Do not connect bare sensor ICs directly using this breakout-board wiring.

### Shared I2C sensors

| Module pin | ESP32-S3 |
|---|---|
| MAX30102 SDA | GPIO 4 |
| MAX30102 SCL | GPIO 5 |
| MAX30102 GND | GND |
| MAX30102 VCC/VIN | 3V3 only if the breakout supports 3.3 V supply |
| MAX30102 INT | Leave unconnected |
| MLX90614 SDA | GPIO 4 |
| MLX90614 SCL | GPIO 5 |
| MLX90614 GND | GND |
| MLX90614 VCC/VIN | 3V3 only for a compatible 3.3 V module |

Both sensors share the same two signal wires. I2C pull-ups must go to 3.3 V. Expected addresses: MAX `0x57`, MLX `0x5A`. MAX30100 is not supported by this library. A 5 V MLX90614 variant needs suitable power and level translation; the 3.3 V wiring above is conditional on the actual module.

### DS1302 clock (five-pin module)

| Module pin | ESP32-S3 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| CLK / SCLK | GPIO 6 |
| DAT / IO | GPIO 7 |
| RST / CE | GPIO 14 |

The DS1302 is not I2C and does not appear in the address scan. This sketch disables trickle charging for the non-rechargeable CR2032 used previously. Clock validity checks cannot conclusively detect every disconnected/faulty DS1302.

### Display option 1: previous ST7789 240 x 280 SPI TFT

| Display pin | ESP32-S3 |
|---|---|
| GND | GND |
| VCC | 3V3 for a compatible module |
| SCL / SCK / CLK | GPIO 12 |
| SDA / DIN / MOSI | GPIO 11 |
| RES / RST | GPIO 8 |
| DC / A0 | GPIO 9 |
| CS | GPIO 10 |
| BL / BLK | 3V3 only if this is a supported backlight supply/control input |

On this **SPI display**, SDA means MOSI and SCL means SPI clock. Do not connect them to the I2C sensor wires. Follow the module's backlight circuit requirements; a bare LED backlight may need current limiting/driver circuitry. If the display has DC but no CS, set `TFT_CS = -1` and leave GPIO 10 unconnected. If it has CS but no DC, this driver/wiring cannot be assumed correct: confirm the controller and interface first.

### Display option 2: SSD1306 128 x 64 I2C OLED

Use this table only with `DISPLAY_KIND 2`.

| OLED pin | ESP32-S3 |
|---|---|
| GND | GND |
| VCC | 3V3 for a compatible module |
| SCL | GPIO 5 |
| SDA | GPIO 4 |

This OLED shares the sensor I2C wires. Do not also connect the TFT table when using this option.

### SPI microSD module

| SD module pin | ESP32-S3 |
|---|---|
| GND | GND |
| VCC | Module-rated supply; see below |
| SCK / CLK | GPIO 40 |
| MOSI / DI | GPIO 41 |
| MISO / DO | GPIO 42 |
| CS / SS | GPIO 21 |

The SD module uses an **independent SPI bus**, so it can coexist with a display that has no CS pin. GPIO 40, 41, and 42 must be exposed and free on your particular ESP32-S3 board. These connections replace any earlier shared-SPI SD wiring suggestion.

For a native 3.3 V microSD breakout, connect VCC to 3V3. Some larger Arduino SD modules have a regulator and expect 5 V at VCC; supply those according to their specification and verify 3.3 V compatible signals (including MISO). Supplying such a regulator board with 3.3 V can undervolt the card. Never connect a bare SD card to 5 V.

Use a FAT32-formatted card; an 8-32 GB card is a straightforward choice. The sketch uses Arduino ESP32's built-in `SD` and `SPI` libraries, not `SD_MMC`.

### External RGB LED

| Connection | ESP32-S3 |
|---|---|
| Red anode through its own 220-330 ohm resistor | GPIO 16 |
| Green anode through its own 220-330 ohm resistor | GPIO 17 |
| Blue anode through its own 220-330 ohm resistor | GPIO 18 |
| Common cathode | GND |

For a common-anode RGB LED, connect common to 3V3 and set `RGB_COMMON_ANODE = true`; each channel still needs its own resistor. This is not the board's addressable onboard RGB LED.

### Two-pin buzzer using an NPN transistor

| Connection | Destination |
|---|---|
| GPIO 15 | 1 kohm resistor, then transistor base |
| NPN emitter | GND |
| NPN collector | Buzzer negative |
| Buzzer positive | Its rated supply |
| Base pull-down | 10 kohm from base to GND |

Use a suitable transistor, for example a 2N2222, checking its actual pinout. For a magnetic/inductive buzzer, add a flyback diode across the buzzer (striped cathode to buzzer positive). Supply ground must join ESP32 ground. Do not power a buzzer directly from a GPIO. Default `ACTIVE_BUZZER = true`; set false for a passive piezo to use a 2 kHz tone.

If using a three-pin buzzer module with an onboard driver, connect S/IN to GPIO 15, GND to GND, and VCC to its specified supply. Defaults assume an active-high module/driver. For an active-low active buzzer module, set `BUZZER_ACTIVE_LOW = true`. The exact buzzer module has not yet been confirmed; check its labels/rating before powering it. The firmware makes only a brief startup test beep.

Do not leave the old parallel 16 x 2 LCD connected: it occupies GPIO 8-13 now used by the screen and SD card.

## Arduino setup and upload

1. Open `neoguard_system.ino` in Arduino IDE. Select the actual **ESP32-S3** board/port and the correct flash/PSRAM settings for that board. These pins are not a wiring plan for the original ESP32 or ESP32-C3. Enable USB CDC On Boot if using native USB serial.
2. Install these libraries through Library Manager: **Adafruit GFX Library**, **Adafruit ST7735 and ST7789 Library** (display option 1), **Adafruit SSD1306** (display option 2), **Adafruit MLX90614 Library**, **SparkFun MAX3010x Pulse and Proximity Sensor Library**, and **Rtc by Makuna**. Accept dependencies such as Adafruit BusIO. ESP32 support supplies Wire, SPI, FS, and SD.
3. Confirm `DISPLAY_KIND`, display dimensions/address, module voltage requirements, and every connection above.
4. Set the RTC using `sync_rtc.ps1` as described above. The helper converts the computer clock to **Africa/Nairobi (UTC+03:00)** regardless of the Windows display timezone. Check that the computer's current time is correct first.
5. Open Serial Monitor at **115200 baud**. Check the detected I2C addresses and component startup status. An SPI TFT does not provide a detection acknowledgement, so `display_init=1` does not prove the screen is connected.
6. Check the display and startup beep. For the bench pulse test, place an adult finger gently and hold still. It takes at least four seconds of continuous samples before the first estimate; low signal or movement may keep readings invalid.
7. With the card fitted and default `ENABLE_SD_LOGGING = true`, expect **SD LOGGING** and an increasing saved-row count. After stopping power, remove the card and open `neoguard.csv` in a spreadsheet. If the footer says **SD NOT READY**, check format, supply, and wiring before trusting that readings were saved.

## Logs and status

CSV columns include a random boot identifier, row number, uptime, local RTC date/time, temperature readings, pulse estimates, contact/raw light readings, and validity flags. Timestamps are local Nairobi time **only if the RTC was set accordingly**; they are not UTC. When the clock is invalid, the timestamp is blank and uptime remains available. Invalid vital estimates are blank rather than reported as zero. Temperature-valid means a finite reading within the sensor's operating range, not a clinical plausibility or calibration check.

The file appends across restarts. The boot identifier and uptime help separate restarts, but are not a secure event/session identifier. Keep the card private if you later associate logs with patients. No patient identifiers are written by this sketch.

- Red: a detected sensor/clock fault, missing pulse data, or a storage fault when SD logging is enabled.
- Blue: waiting for valid pulse estimates when the other checks pass.
- Green: both pulse estimates available and the component checks pass.

The SD file is flushed and closed after each row. A failed SD initialization/write causes retry every ten seconds; rows produced while storage is unavailable appear on Serial only and are **not replayed** later. Stop power before inserting/removing the card. Abrupt power loss can still lose/corrupt the last write. Slow SD operations can interrupt pulse sampling; the sketch discards the pulse window after a service gap of 120 ms or more and rebuilds it, accounting for the pulse library's small software buffer. This single-loop design is a bench integration, not guaranteed real-time acquisition.

There are no automatically selected neonatal alarm thresholds or continuous buzzer alarms. Sensor failures detected at startup require checking connections and restarting after fixing the hardware.

## Reference interfaces

- [Espressif SD library and custom SPI pins](https://github.com/espressif/arduino-esp32/blob/master/libraries/SD/README.md)
- [Adafruit ST7789 example and display sizes](https://github.com/adafruit/Adafruit-ST7735-Library/blob/master/examples/graphicstest_st7789/graphicstest_st7789.ino)
- [SparkFun pulse/SpO2 reference algorithm](https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library/blob/master/src/spo2_algorithm.h)
