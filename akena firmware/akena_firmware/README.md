# Akena NeoGuard full LCD integration

Updated 22 October 2026. Experimental bench prototype; readings and alarms are not validated for clinical use. MLX90614 measures surface/object temperature, not core temperature. This revision replaces the ST7789 display with the original 16x2 parallel LCD and preserves the other established pins. No simulated readings are generated.

## Wiring

Disconnect power before wiring. All module grounds join ESP32-S3 GND. Use GPIO labels, not header position numbers.

| Component | Connections |
| --- | --- |
| LCD 16x2 | RS pin4 -> GPIO8; EN pin6 -> GPIO9; D4 pin11 -> GPIO10; D5 pin12 -> GPIO11; D6 pin13 -> GPIO12; D7 pin14 -> GPIO13 |
| LCD power/control | VSS pin1 -> GND; VDD pin2 -> rated 5V supply; RW pin5 -> GND; VO pin3 -> 10k potentiometer middle; pot outer legs -> 5V and GND; pins7-10 unused |
| LCD backlight | A pin15 -> 5V through 220 ohms; K pin16 -> GND; confirm actual module specification |
| MAX30102 | SDA -> GPIO4; SCL -> GPIO5; INT unused; supply at verified module voltage |
| MLX90614 | SDA -> GPIO4; SCL -> GPIO5; supply at verified module voltage |
| DS1302 | CLK -> GPIO6; DAT -> GPIO7; RST/CE -> GPIO14; VCC -> 3V3; GND -> GND |
| microSD | CS -> GPIO21; SCK -> GPIO40; MOSI/DI -> GPIO41; MISO/DO -> GPIO42; supply at verified module voltage |
| RGB common cathode | R -> GPIO16; G -> GPIO17; B -> GPIO18, each through its own 220–330 ohm resistor; common -> GND |
| Two-pin buzzer control | GPIO15, active-high default; rated supply and NPN driver recommended as previously described |

For common-anode RGB, set `RGB_COMMON_ANODE = true` and common -> 3V3. For a passive piezo buzzer, set `ACTIVE_BUZZER = false`. Direct GPIO buzzer drive is only suitable when its electrical specifications permit it; working audibly does not establish safe current draw. Confirm transistor pinout if fitting a driver.

ESP32 signals are 3.3V. Keep sensor SDA/SCL pull-ups at 3.3V. A 5V LCD must accept 3.3V logic or use a suitable 3.3V-to-5V buffer on its six control/data lines. RW remains grounded. Disconnect the old screen completely because its GPIO8-12 now belong to the LCD. Do not connect an external positive supply rail to the USB-powered board's power outputs.

## Build and upload

1. Open `akena_firmware.ino` with every sibling header present.
2. Select **ESP32S3 Dev Module**, the actual board's flash/PSRAM settings and its serial port. Enable **USB CDC On Boot** for native USB Serial Monitor. Do not guess flash size/PSRAM from the board menu name.
3. Install libraries: **LiquidCrystal by Arduino**, **SparkFun MAX3010x Pulse and Proximity Sensor Library**, **Adafruit MLX90614 Library**, **Rtc by Makuna**, **ArduinoJson 7**, and **WiFiManager by tzapu 2.0.17**. Wire, SPI, SD, WiFi and Preferences come with ESP32. This sketch no longer requires a TFT/OLED graphics library.
4. Upload, then open Serial Monitor at **115200 baud**, newline enabled. Press reset if necessary. The startup marker is `NEOGUARD FULL FIRMWARE LCD`.
5. Adjust the contrast potentiometer until the LCD text is visible. Initialization success cannot confirm physical LCD operation because RW is grounded.

## Phone Wi-Fi setup

1. On first boot, or when saved Wi-Fi is unavailable, the device advertises **NeoGuard-XXXX**. LCD pages rotate every four seconds through the network name, unique saved AP password, **192.168.4.1**, and instructions. Serial Monitor also prints these details.
2. Connect the phone to that network. Choose to stay connected if warned there is no internet.
3. Open **http://192.168.4.1** if the sign-in page does not open automatically. Select **Configure WiFi** and choose your **2.4 GHz** router network. Enter its password.
4. Enter the registered dashboard **device code** and **device secret** in the same form. This secret is not your dashboard login password. Keep the default API URL `https://neoguard-api-wwth.onrender.com/api/v1` when using the existing hosted frontend/backend. A different backend requires its own device registration and matching HTTPS trust configuration.
5. Save and allow the device to restart. It remembers the Wi-Fi and device settings. The phone can then return to its normal network.
6. To reopen configuration later, send **WIFI SETUP** followed by a newline in Serial Monitor. A different device code needs its own secret; a blank secret only preserves the existing secret for the same code.

Wi-Fi provisioning uses WiFiManager: https://github.com/tzapu/WiFiManager . LCD driver: https://docs.arduino.cc/libraries/liquidcrystal/ . Acquisition runs in its own task while phone setup and network requests run separately.

## Get real readings onto the frontend

1. Open the matching dashboard: **https://neoguard-ai-lovat.vercel.app** for the default cloud API.
2. An administrator must register and activate the device in the intended clinic. Save the issued device code and one-time device secret, and enter them in the phone setup form. Do not reuse credentials issued by a different local backend.
3. Using the appropriate clinical account, create/select the intended patient and start an active monitoring session assigned to that device. Existing patient/clinic data should only be used for its intended session; use an authorized bench/test record for bench readings.
4. The ESP32 discovers its active session automatically about every ten seconds. It uses authenticated HTTPS, network time and the existing runtime endpoint, with compatibility fallback for the earlier cloud API.
5. For a bench check, hold an adult finger still on the MAX30102 and aim the MLX90614 steadily at the intended test surface. Allow at least 60 seconds. All three channels must meet the existing validity and stability gates before combined readings qualify. Waiting alone does not guarantee a result.
6. Qualified measurements are queued every five seconds and sent in acknowledged batches. Watch Serial Monitor for **SYNC: batch acknowledged** or **SYNC: RAM batch acknowledged**. On the nurse/clinician patient-detail page, choose a time range containing the current measurements and watch the readings refresh. The administrator registry is not the patient vitals view.
7. Send **STATUS** to inspect Wi-Fi, IP, portal activity, credential presence, session ID, RTC, SD, sensor state, measurement readiness and upload status. It does not print device secrets. `configured=1` only means credentials are present, not that the server accepted them.

Common blockers:

- `session=0` / `NO ACTIVE SESSION`: check registration, activation, device secret, clinic and assigned monitoring session on the same backend.
- `DEVICE AUTH ERROR` or HTTP 401/403: verify the correct device secret and active registration.
- `ready=0`: inspect finger contact, raw sensor validity and the signal countdown. Measurements are not fabricated or sent as valid simply to fill the graph.
- `RTC=0`: allow network/session time sync, or send `TIME YYYY-MM-DD HH:MM:SS` using Nairobi local time. `TIME?` reads the clock; `sync_rtc.ps1` can set it from this computer. The CR2032 trickle charger remains disabled.
- Negative HTTP codes / TLS failure: check Wi-Fi, internet access, clock and the embedded certificate in `root_ca.h`. TLS verification is not disabled.
- `SD=0`: check FAT32 formatting, module-rated supply, shared ground and the four SD signal wires. Up to 12 events can remain temporarily in RAM; they do not survive power loss.
- Missing frontend readings despite acknowledged uploads: verify the same patient session, backend, date range and clinician account. Local frontend preview must be disabled (`VITE_DASHBOARD_PREVIEW=false`).

## LCD, storage and alarms

The LCD rotates measurement/countdown, date/time, Wi-Fi/IP and SD/upload pages. Alarm and sensor-fault messages take priority. During phone setup it rotates the AP instructions and sensor status.

The original signal check requires at least 45 valid one-second observations in a minute, with at least 12 in the latest 15 seconds and limited recent variation. Qualified medians update every five seconds. Removal, stale sampling or instability clears readiness. This checks repeatability, not clinical accuracy.

Existing project limits remain HR below 100 or above 160 bpm, surface temperature below 36.5 C and SpO2 below 90%, unless the authenticated server supplies configured limits. Three consecutive valid breaches trigger the red LED and pulsed buzzer; missing sensors also signal faults. An adult bench pulse may trigger the neonatal prototype's low-HR alarm. Blue indicates acquisition, not health.

The FAT32 card records `/neoguard_v2.csv`, including raw values and validity flags. `/pending.ndjson` retains upload events with their original session/time and immutable IDs; `/sync.cursor` advances only for acknowledged events. Retries reuse event IDs. Existing CSV files are preserved; the firmware does not format the card. Rejected/corrupt queue data is retained for inspection. Power down before removing the card.

## Data for machine learning

This firmware collects real bench sensor observations; it does not train a model or label outcomes. Preserve raw values, timestamps, validity, session identity, sensor placement and independently established labels when preparing a dataset. Repeated samples from one short bench session are not evidence of a clinically useful model. Do not train on invalid measurements or treat surface temperature as core temperature.

See `BUILD_CHECK.txt` for the current software verification. Preparing or compiling firmware does not flash the board, register a device, assign a session or prove that hardware readings have reached the hosted frontend.
