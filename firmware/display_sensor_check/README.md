# Display, temperature and oximeter check -- no Wi-Fi

Open `display_sensor_check.ino` in Arduino IDE. This is a separate sketch and does
not change the main firmware sources. Uploading replaces the program on the board.

The target is the earlier **ST7789 240x280 SPI screen**, previously called OLED in
the project. A four-pin SSD1306/SH1106 OLED needs different code and wiring. This
screen has no touch-input connection: a display interaction means a serial D command,
not touching the glass. Visible colour/text and advancing uptime are the display test;
sending drawing commands cannot prove that a physical screen is working.

## Same connections

Disconnect power while wiring. Remove the parallel LCD connections first. Join all
grounds and use GPIO labels on the ESP32-S3, not physical header position numbers.

| Part | Connection |
|---|---|
| ST7789 RST / RES | GPIO8 |
| ST7789 DC | GPIO9 |
| ST7789 CS | GPIO10 |
| ST7789 SDA / MOSI | GPIO11 |
| ST7789 SCL / SCK | GPIO12 |
| ST7789 VCC / GND | 3.3V-compatible breakout supply / common GND |
| MLX90614 SDA / SCL | GPIO4 / GPIO5 |
| MAX30102 SDA / SCL | GPIO4 / GPIO5 |
| Sensor VCC / GND | Verified 3.3V-compatible breakout supply / common GND |
| Buzzer control | GPIO15 through existing transistor driver |

For a two-pin active buzzer, use GPIO15 -> 1k resistor -> PN2222A base; base -> 10k
to GND; emitter -> GND; collector -> buzzer minus; buzzer plus -> rated supply.
Diode striped end -> buzzer plus, other end -> collector. Verify transistor pinout;
the project's carrier assumes a buzzer load of at most 20mA. Do not assume an unknown
buzzer is suitable for direct GPIO drive. ACTIVE_BUZZER=true and BUZZER_ACTIVE_LOW=false
match the existing active-high driver. A compatible passive-piezo driver can use
ACTIVE_BUZZER=false. All ESP32 and I2C signals must remain at 3.3V levels.

If the display has BL/BLK/LED, follow the breakout's documented backlight requirements;
no backlight GPIO is controlled here. A bare LED needs current limiting. The screen's
SPI labels SDA/SCL are not the sensors' I2C bus. SD/RTC/RGB are not tested by this sketch;
SD chip select is held high to leave an attached SD module deselected.

## Libraries and upload

Install in Library Manager (with requested dependencies):
- Adafruit GFX Library
- Adafruit ST7735 and ST7789 Library
- Adafruit MLX90614 Library
- SparkFun MAX3010x Pulse and Proximity Sensor Library

Wire, SPI and FreeRTOS are included with the ESP32 board package. Choose ESP32S3 Dev
Module, the actual flash/PSRAM settings and correct port. Enable USB CDC On Boot when
using native USB serial. Upload, open Serial Monitor at **115200 baud**, select a
newline line ending, and reset the board if needed to see startup messages.

## Interactions and beeps

The screen first flashes red/green/blue, then displays live readings. A short beep
accompanies the display test. All readings repeat in Serial Monitor too.

| Action | Expected response |
|---|---|
| Send D or SCREEN | Beep, draw RGB bars, increment screen test count |
| Send T or TEMP | Beep, print current temperature/sensor snapshot |
| Send O or OXI | Beep, print current oximeter/sensor snapshot |
| Send B or BUZZ | One short beep to test buzzer/driver |
| Place a stationary adult finger on MAX30102 | Beep on confirmed contact; collect a four-second window, then attempt HR/SpO2 estimates |
| Remove finger, then place again | Contact re-arms and beeps on the next placement |
| Present a nearby warm hand/object to MLX90614 | Beep once when object exceeds ambient by 1.5 C for about 0.6 seconds |
| Aim MLX back at surroundings, then present warm object again | Re-arms below ambient+0.7 C, then beeps on next warm target |
| Send HELP | Print command help |
| Send S or SCAN | Scan the I2C bus, print idle SDA/SCL levels and responding addresses |

The MLX has no touch/proximity detector. The warm-target rule is a test heuristic;
it will not recognize every object or every gesture. If the object is not warmer
than ambient, use T for an explicit test/beep. Thresholds are constants at the top
of the sketch, not clinical limits. Warm-target beeps can occur automatically after
startup if a warm object is already in view. Nearby simultaneous events may share
a beep. The buzzer is not a heartbeat or medical alarm.

MAX contact uses adjustable raw IR thresholds (on 50000, off 40000) and short
confirmation/hysteresis. Adjust only after comparing uncovered and covered raw
readings for the actual breakout. Hold still and shield from excessive ambient light.
The red/IR sampling runs separately from screen drawing. Estimates require a full
25 Hz, 100-sample window and algorithm validity flags. Motion, weak signals or missing
samples leave `--`; the code does not fabricate values. The algorithm's valid flag
does not establish measurement accuracy or clinical validity.

MLX object temperature is **surface temperature**, not core temperature. Use this
sketch to check wiring, activity and basic repeatability, not clinical suitability.
Temperature values are hidden after two seconds without a valid reading. The I2C
scan runs at startup and on S; a requested scan can briefly interrupt pulse sampling.
If the scan finds no addresses, investigate power, common ground and SDA/SCL wiring;
this result alone does not establish that either sensor is defective.
If a sensor is missing, disconnect power, correct wiring and reset. No Wi-Fi, cloud
credentials, RTC or SD card are required. See BUILD_CHECK.txt for compile status.
