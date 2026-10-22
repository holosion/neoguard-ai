# Working NeoGuard sketch: blue status, SD storage and Wi-Fi replay

Open **sketch_oct12a.ino** in this folder. Keep **display_icons.h** and **offline_sync.h** beside it. Your original sketch is backed up as **sketch_oct12a.before-blue-sd-sync.ino.bak**. The original code matched the pasted working code after newline normalization. The icon file is unchanged.

## Light and thresholds

- **Blue:** the temperature sensor provides a valid reading and the MAX sensor is delivering samples. Waiting for a finger or for pulse estimates also uses blue.
- **Red:** invalid/missing temperature sensor, missing MAX sensor, or no MAX samples for more than two seconds. Serial Monitor explains which check failed.
- The clock, SD card and network have separate display/serial status. Their failure no longer turns the sensor-status LED red. Blue describes hardware operation, not patient health or successful storage/upload.

All original bench limits remain unchanged: contact IR >= 50000; HR validity > 0 and <= 250; SpO2 validity 0–100; object-temperature validity -70–380 C; ambient-temperature validity -40–125 C. These are contact/validity checks, **not neonatal clinical alarm thresholds**. The pasted sketch has no clinical alarm threshold logic. Backend/dashboard alert thresholds are unchanged. The startup beep is unchanged.

The ST7789 240x280 display, sensor pins, sampling settings, icons and main layout stay the same. The bottom line now shows clock/upload status. If the physical RGB color differs from the requested color, check GPIO16=red, GPIO17=green, GPIO18=blue and common-anode/cathode wiring.

## Breadboard supply and SD module

Disconnect power before wiring or inserting/removing the card. Use the existing module's rated input supply: a regulator-equipped module may require 5 V at its supply input, while a native 3.3 V breakout requires 3.3 V. Do not infer the voltage from the module's color. Keep the sensors on their established compatible supplies and ESP32 signals at 3.3 V logic. Join the breadboard supply ground, SD ground and ESP32 ground. Check voltage at the module itself and check for split breadboard rails. Do not tie external regulated positive rails to a USB-powered ESP32's power outputs.

| SD module pin | ESP32-S3 |
| --- | --- |
| CS | GPIO21 |
| SCK / CLK | GPIO40 |
| MOSI / DI | GPIO41 |
| MISO / DO | GPIO42 |
| GND | Shared GND |
| VCC | Module-rated supply |

Use an existing FAT32-formatted card; the sketch never formats a card. It attempts mounting at 1 MHz, then 400 kHz, verifies the CSV header after opening, and retries a failed card every ten seconds. It cannot correct incorrect wiring, unsuitable power, a damaged module or card. Serial Monitor at 115200 shows mount/open/write errors; the display shows **SD LOGGING #N** when CSV rows are being written. N counts CSV writes during this boot, not uploads.

CSV readings append to **/neoguard.csv** approximately once a second without internet. Invalid values remain blank with their original validity flags. An unset RTC produces a blank CSV timestamp. The file is flushed and closed after each row; sudden power loss can still interrupt a write. A card failure means subsequent readings cannot be saved until storage recovers. Do not hot-swap cards; reboot after changing a card.

## Enable SD-to-dashboard uploads

1. In the dashboard, use the registered device's **device code and device secret**, and start the intended monitoring session. A dashboard login password is not a device secret. Note that session's numeric ID.
2. Copy **sync_config.example.json** to the root of the SD card and rename the copy **sync_config.json**. Enter the 2.4 GHz Wi-Fi name/password, backend API base URL, registered device code/secret and actual positive session ID. The example's session ID 0 intentionally disables uploads until configured. Never commit the filled configuration or share its secrets in chat.
3. Copy **root_ca.pem** from this folder to the root of the SD card. This public certificate was taken from the backend's system-verified trust chain; a separate TLS handshake verified it on 20 October 2026. If using another backend/certificate authority, replace this with its appropriate trusted root. HTTPS certificate verification stays enabled. Internet time synchronization is used for TLS; blocked NTP or a changed certificate chain can prevent uploads.
4. Install **ArduinoJson 7** alongside the libraries used by your working sketch. Select your existing ESP32-S3 board/port settings and upload **sketch_oct12a.ino**. Keep USB CDC On Boot enabled when using native USB serial.
5. Set the DS1302 to correct current Nairobi time before collecting readings. Use the included **sync_rtc.ps1** helper, or send `TIME YYYY-MM-DD HH:MM:SS` with the actual time and a newline at 115200 baud. No date/time is hard-coded. The RTC must be valid to queue upload events.
6. Check **SD LOGGING**. When readings can be queued, the bottom line shows **SYNC SENDING**, **SYNC UPLOADED**, **SYNC WAIT WIFI** or **SYNC RETRY**. **SYNC SETUP NEEDED** means configuration/certificate is missing or incomplete; CSV logging still works.

Configuration is loaded at startup (or when a previously unavailable SD card first recovers). After editing a configuration, reboot. A valid configuration must be present **before** collecting readings intended for automatic upload. CSV rows collected without configuration or a valid RTC are retained locally but are not converted into upload events later.

## Offline replay behavior

- **/pending.ndjson** stores upload events on SD before sending, with random UUIDs, original session IDs and timezone-aware Nairobi observation times. Wi-Fi requests run on a separate task; only the main loop accesses the SD card.
- The backend accepts HR 40–220, SpO2 50–100 and temperature 30–42 C. Values outside those input limits stay in the CSV and are omitted from upload fields; values are never clamped or replaced. At least one eligible field is needed for an upload event. A partial event has quality `poor`. This does not alter the original on-device validity checks or backend thresholds.
- Every 15 seconds, up to 20 queued events are offered to `/api/v1/devices/sync`. The device advances **/sync.cursor** only after the response matches the batch and every event is `accepted` or `duplicate`, and the cursor write succeeds. Disconnects, timeouts and failures retain the batch for retry. Duplicate retries use the same event UUIDs, so the existing backend avoids adding duplicate readings. File contents are retained even after successful upload.
- Checkpoint damage falls back to replay from the beginning. Incomplete/corrupt queue records show **SYNC FILE CHECK** and stop automatic queue use; preserve the card files for recovery. Files are not automatically erased, repaired, or reassigned. A rejected batch remains in place and prevents later batches from passing it; inspect serial output and the session/clock/configuration before resuming.
- Before moving the device to another patient, stop collection, finish/reconcile the old queue, stop the old session and start the new session in the dashboard. Update the SD configuration with the **new** session ID, then reboot before collecting for that patient. Old events retain their original session ID. Never replace their session IDs to force upload. The backend rejects timestamps outside the original session window.
- Preserve **pending.ndjson** together with **sync.cursor**. Do not delete or replace either while running. There is no automatic log rotation; back up and manage storage before the FAT32 file limit or card capacity is reached. Credentials are stored as plain text on the card, so keep possession of it.

## Bench verification on the assembled device

1. With valid configuration/clock/session, record several adult-finger bench readings. Confirm blue and an increasing CSV count; Serial Monitor must show no sensor faults.
2. Turn off the Wi-Fi access point for one minute. Confirm CSV and pending-file growth. Power down cleanly, reboot with Wi-Fi still off, and confirm acquisition resumes from the retained queue.
3. Restore Wi-Fi. Confirm acknowledged batches in Serial Monitor and corresponding historical readings in the same dashboard session. Observe that the queue progress catches up, then interrupt Wi-Fi during a batch and check that retry does not add duplicate events.
4. Power down, inspect the SD files on a computer, and confirm CSV values and original timestamps/session IDs in queued records. Do not edit event IDs or cursor offsets.
5. Verify missing/failed storage stays visible separately from sensor status. A real sensor fault should still show red.

SD writes and file reading can still delay the single acquisition loop. The existing pulse-window reset on sampling gaps remains in place; this is not a real-time or clinically validated neonatal monitor. Compilation, backend contract tests and desktop TLS checks cannot establish physical SD operation, sensor accuracy or live authenticated replay from the ESP32.
