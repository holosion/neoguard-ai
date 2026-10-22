# DS1302 RTC wiring for the neonatal bench test

The pictured five-pin RTC module is treated as a DS1302. This sketch targets the existing ESP32-S3 setup.

| RTC label | ESP32-S3 connection |
| --- | --- |
| VCC | 3.3V |
| GND | GND |
| CLK (SCLK) | GPIO 6 |
| DAT (IO) | GPIO 7 |
| RST (CE) | GPIO 14 |

Use the printed pin labels, rather than wire colors. The pin assignments can be changed with RTC_CLK, RTC_DAT, and RTC_RST at the top of system_test.ino. These assignments avoid the LCD, sensors, buzzer, and RGB pins already used in this sketch.

Install **Rtc by Makuna** using the Arduino Library Manager. It replaces the previous RTClib dependency for this sketch. Keep the existing LiquidCrystal, Adafruit MLX90614, and SparkFun MAX3010x libraries installed.

For the first upload, set SET_RTC_TIME to true. The RTC will be set to the computer's local compilation date and time. Ensure the computer clock uses your intended timezone (Africa/Nairobi). After that upload, change SET_RTC_TIME back to false and upload again so restarting the board preserves the battery-backed time.

The DS1302 uses a three-wire interface and will not appear in the I2C scan. If the display says RTC unset/check, verify wiring, battery, and the initial time-setting step. This interface cannot reliably distinguish a disconnected clock from an unset clock.

The pictured CR2032 is non-rechargeable; the sketch disables the DS1302 trickle charger.
