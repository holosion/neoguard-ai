# NeoGuard full ST7789 monitor with Wi-Fi

Rebuilt 24 October 2026 for the tested ESP32-S3 and **ST7789 240x280 SPI screen**,
previously called OLED in the project. The LCD firmware is backed up under
`.local/firmware-backups/pre-integrated-st7789-20261024/`. This is a bench prototype;
software stability qualification is not clinical calibration or validation.

The default is now **NEOGUARD_ENABLE_NETWORK=1**, following the successful offline
dashboard, measurement-removal and alarm checks. Sensors, DS1302 clock, RGB/buzzer,
display and SD logging operate alongside Wi-Fi and secure backend syncing.
Existing saved network/device settings and pending uploads are reused. Set the
option to 0 and rebuild to return to the isolated offline build.

## Wiring

Use GPIO labels, not physical header positions. Disconnect power before rewiring
or removing the SD card. All module grounds connect together.

| Part | Connection |
|---|---|
| ST7789 RST / DC / CS | GPIO8 / GPIO9 / GPIO10 |
| ST7789 MOSI (SDA) / SCK (SCL) | GPIO11 / GPIO12 |
| ST7789 VCC / GND | Verified 3.3V-compatible breakout supply / common GND |
| MAX30102 SDA / SCL | GPIO4 / GPIO5; INT unused |
| MLX90614 SDA / SCL | GPIO4 / GPIO5 |
| Sensor VCC / GND | Verified 3.3V-compatible breakout supply / common GND |
| DS1302 CLK / DAT / CE | GPIO6 / GPIO7 / GPIO14; VCC=3.3V, GND common |
| microSD CS / SCK / MOSI / MISO | GPIO21 / GPIO40 / GPIO41 / GPIO42 |
| microSD VCC | Actual breakout's rated supply; ESP32-compatible signals |
| RGB R / G / B | GPIO16 / GPIO17 / GPIO18, each through 330 ohms |
| RGB common cathode | GND; RGB_COMMON_ANODE=false |
| Buzzer control | GPIO15 through the verified active-high driver |

Disconnect the parallel LCD because its GPIOs overlap the ST7789. GPIO13 is unused.
Screen SDA/SCL labels describe SPI; they do not connect to sensor I2C SDA4/SCL5.
Use the verified screen breakout's backlight requirements; no backlight GPIO is
configured. Never pull I2C to 5V.

The established buzzer driver uses GPIO15 through 1k to PN2222A base, 10k base to
GND, emitter to GND, collector to buzzer minus, buzzer plus to its rated supply,
and diode striped end to buzzer plus/other end to collector. Verify transistor
pinout; the carrier assumes a buzzer load at most 20mA. Carrier SD JP2 pins1-2
selects 3.3V; pins2-3 selects 5V; fit one shunt using the actual breakout rating.

## Upload

Open `akena_firmware.ino` with every sibling header present. Select ESP32S3 Dev
Module, actual flash/PSRAM settings and correct port. Enable USB CDC On Boot for
native USB serial. Install the following libraries and their dependencies:

- Adafruit GFX Library
- Adafruit ST7735 and ST7789 Library
- Adafruit MLX90614 Library
- SparkFun MAX3010x Pulse and Proximity Sensor Library
- Rtc by Makuna

Wire, SPI, SD, WiFi and HTTPS support come with ESP32. The network build also needs
ArduinoJson 7 and WiFiManager by tzapu 2.0.17. LiquidCrystal is not required.

Upload and open Serial Monitor at **115200 baud**, newline enabled. Startup says
`NEOGUARD FULL FIRMWARE ST7789 - network=1`. This screen has no readback or touch input.

## Wi-Fi and backend setup

Saved Wi-Fi settings reconnect automatically. If setup is needed, the screen shows
a password-protected `NeoGuard-XXXX` network and its setup password. Join that
network from a phone, then open `http://192.168.4.1`. Choose a 2.4 GHz Wi-Fi network
and enter its password. Wi-Fi can be used with both device fields blank; the
dashboard remains available after reconnect. For backend syncing, configure the
dashboard's device code and corresponding device secret; blank secret keeps the
saved secret for the same device code. The
default HTTPS API is `https://neoguard-api-wwth.onrender.com/api/v1`.

Send `WIFI SETUP` to reopen configuration. The setup page replaces the dashboard
while active; sensor acquisition, local CSV recording and alarms continue. Saved
device-setting changes restart the board after the current SD operation closes.
Wi-Fi passwords and device secrets are never embedded in the sketch.

If DHCP leaves the DNS server unset (`0.0.0.0`), the network worker retains any
secondary resolver or falls back to 1.1.1.1 and 8.8.8.8. A supplied primary DNS
server is preserved. This keeps DHCP addressing and HTTPS certificate/hostname
verification enabled. Failed requests print bounded DNS/TCP diagnostics without
credentials. Networks that block public DNS must supply a working local resolver.
Backend replies are decoded through HTTPClient's streaming reader, including
chunked responses without Content-Length, with a 20000-byte response limit.

An internet connection, valid device credential and active dashboard session are
required to deliver sensor readings. The network worker checks the server context,
reports connectivity with heartbeats, and uploads available sensor values from the
SD queue. Unqualified live estimates carry `quality=poor`; only measurements that
pass the full stability checks carry `quality=ok`. Missing parameters are omitted,
and values outside the API bounds are never clamped. Only a complete server
acknowledgement advances the queue cursor. Loss of
Wi-Fi leaves local monitoring and SD logging running. No artificial readings are
generated to test delivery. If SD fails, the upload fallback holds only 12 readings
in RAM; check STATUS for dropped readings.

## Display and measurement rules

The dashboard shows clock, averaged HR, live SpO2, surface temperature, acquisition
status, saved-row count and connectivity. MLX90614 measures surface temperature.
HR uses the arithmetic mean of valid, distinct algorithm estimates from the last
10 seconds, published every three seconds. At least five estimates spanning four
seconds are needed before the first average; the sensor also needs its initial
four-second acquisition window. The screen labels this `HEART RATE / 10s AVG`.
Finger removal, invalid signal or an estimate older than two seconds clears the
displayed average. A long signal gap resets its history. No zero-filled missing
samples, frozen values or clamping are used. SpO2 remains independent. Moving the
temperature target does not hide a valid pulse estimate.

This average smooths the display only. Raw readings still drive alarms, the full
qualification check, the existing CSV fields and backend uploads. A calmer
display does not make an unstable signal qualified or eligible for AI scoring.

The separate qualified measurement indicator still requires:

- Continuous finger contact for at least 60 seconds.
- At least 45 valid observations in the latest minute.
- At least 12 valid observations in the latest 15 seconds.
- Recent HR spread at most 12 bpm, oxygen spread at most 3 percentage points,
  and temperature spread at most 0.4 C.

Qualified medians update every five seconds. Removal, stale/invalid samples or
excess variation clears readiness. Until qualification passes, the screen labels
the numbers as estimates and the backend marks their quality as poor. A stable
estimate still needs independent accuracy validation. The diagnostic showed
erratic raw HR; these checks remain in place. Raw values remain in STATUS/CSV.
Waiting alone does not guarantee readiness.

MAX sampling runs separately at an effective 25 Hz during display and SD operations.
Contact uses 50000 IR on / 40000 off thresholds, confirmation and saturation
rejection. STATUS exposes sample counts/resets to check acquisition continuity.
Temperature reads check the MLX90614 packet error code and sensor error bit;
failed frames produce an unavailable value and increment the STATUS error counter.
The packet format and reference test vector follow the
[Melexis datasheet](https://www.melexis.com/-/media/files/documents/datasheets/mlx90614-datasheet-melexis.pdf).

## RGB and buzzer

- Blue: averaging, missing/invalid readings or awaiting limit confirmation, without
  a confirmed alarm or fault.
- Green: average available, all three displayed readings fresh and valid, and each
  within the configured limits, with no confirmed alarm or sensor fault. The
  screen says `IN RANGE / ESTIMATE` until full
  qualification passes. Green describes configured ranges, not a diagnosis or AI
  eligibility; raw qualification and upload quality remain separate.
- Red: sensor fault or confirmed threshold alarm.
- Buzzer: startup cue, BEEP command, pulsed threshold alarm or sensor-fault cue.

The requested surface-temperature alarm is strictly below **32 C**; 32 C itself
does not count as low. Backend clinical temperature defaults do not overwrite
this surface setting. HR below 100/above 160 bpm and SpO2 below 90% remain the
prototype defaults, so adult bench HR can still activate the alarm. Each parameter
has independent three-breach/three-recovery confirmation. Invalid values do not
silently clear an existing alarm. Removing the finger resets threshold alarms.

The hosted `BENCH-` patient view distinguishes live estimates from qualified
readings and uses the 32 C surface limit. Other patient views retain their clinical
display rules. The current device is registered as `NG-E1E078` with a clearly
labelled bench session; device secrets stay in private configuration.

## SD logging and commands

The existing `/neoguard_v2.csv` opens in append mode after a header check. No card
formatting occurs. One row per reporting interval contains boot ID, time and RTC
validity, qualified values/flags, raw red/IR, raw estimates, surface observation,
readiness/countdown and alarm flags. Qualified fields stay empty until ready.

| Command | Action |
|---|---|
| STATUS | Hardware/network state, raw values, saved rows, sample counters, heap, HTTP outcomes |
| LOGCHECK | Reopen CSV and compare the latest saved row byte-for-byte |
| SD RETRY | Reinitialize the SD SPI bus and retry the existing CSV mount/check |
| SD QUIET | Diagnostic: pause acquisition, release I2C, test SD, restore sensors |
| BEEP | Request a 300ms beep; alarm output takes priority |
| TIME? | Read DS1302 Nairobi local date/time |
| TIME YYYY-MM-DD HH:MM:SS | Set Nairobi local time and verify readback |
| WIFI SETUP | Open the password-protected phone configuration portal |

`sync_rtc.ps1 -Port COM7` sets RTC from this computer's Nairobi clock. The CR2032
trickle charger stays disabled. Readback and advancing time are checks; battery
retention needs a separate power-loss test. Correct missing-sensor wiring/power
with power off and reset. SD mounts retry every ten seconds with finger removed.

## Validation

BUILD_CHECK.txt and HARDWARE_TEST.md record the actual current results. The small
diagnostic sketches in `firmware/` remain available for component isolation.
Network support is in `offline_sync.h`/`network_setup.h` behind `connectivity.h`.
STATUS reports Wi-Fi/IP, device configuration/session and the most recent runtime,
heartbeat and sync HTTP outcomes. Zero means no attempt yet; -100 means request
prerequisites were unavailable. See the hardware report for checks actually run.

## How the AI fits

The ESP32 calculates the display average and operates RGB/buzzer threshold alarms
locally, including when Wi-Fi is unavailable. The backend's experimental model
uses qualified temperature, oxygen and HR history after successful uploads. It
extracts latest value, mean, direction of change and variability for each signal
from up to two minutes of history. It requires at least 12 valid observations per
signal spanning at least a minute, with gaps no longer than 15 seconds and a valid
latest reading. Poor-quality display estimates are excluded.

When enabled and enough qualified data exists, its output appears in the web
app's Experimental risk score panel. The saved model is trained on simulated data
and targets simulated low-temperature/low-oxygen events now or within 120 seconds.
It is not clinically validated and does not control the ESP32's RGB/buzzer. The
local 32 C surface limit is separate from the model's clinical threshold contract.
See [the AI guide](../../ai/README.md) for model details and availability states.
