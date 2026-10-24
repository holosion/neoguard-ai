# Claude prompt: complete NeoGuard embedded firmware and backend integration

Act as a senior embedded systems software engineer with strong ESP32-S3, Arduino C++, FreeRTOS, sensor acquisition, SPI/I2C displays, persistent storage, HTTPS REST integration, and hardware debugging experience.

I am building **NeoGuard**, an offline-aware neonatal monitoring research prototype. Previous integrated firmware has failed on the assembled system, especially the display. I want you to inspect the supplied code and produce a complete, coherent firmware implementation that operates the existing hardware and communicates correctly with the existing backend. I need all source files, configuration instructions, and an actionable verification procedure. Do not stop at an architecture proposal, isolated snippets, or pseudocode.

Use the supplied project facts and source as your integration contract. Correct defects you find; do not assume previous code works because it compiled. Preserve the existing wiring unless you can demonstrate a conflict and explain a necessary change. Clearly distinguish verified source facts, recorded hardware feedback, assumptions, and items requiring a physical test. Do not claim the hardware works until it has actually been tested.

This is a bench/research prototype. The existing thresholds are provisional project settings, not approved medical recommendations. Optical HR/SpO2 estimates and MLX90614 surface temperature are not clinically validated neonatal measurements. Preserve that distinction in the code, UI labels, and documentation.

## 1. System and current source of truth

The system has these layers:

1. An **ESP32-S3** acquires MAX30102 optical data and MLX90614 object/ambient temperatures, reads a DS1302 RTC, drives the display, RGB indicator and buzzer, logs to microSD, and synchronizes real readings over Wi-Fi.
2. A **FastAPI/Pydantic/SQLAlchemy backend** exposes `/api/v1`, authenticates devices, validates and stores readings in PostgreSQL, generates deterministic threshold alerts, and optionally calculates separate research AI scores.
3. A **React 18/Vite dashboard** provides administrator, clinician and nurse views, device registration, patient/session assignment, readings, trends, alerts and device health.
4. A separate experimental AI model uses simulated research data. Do not move model inference onto the ESP32 or require it for local measurement/alarm operation.

The primary firmware source is:

```text
akena firmware/akena_firmware/
  akena_firmware.ino
  measurement.h
  pulse_sampler.h
  offline_sync.h
  network_setup.h
  runtime_compat.h
  root_ca.h
  README.md
  BUILD_CHECK.txt
  sync_rtc.ps1
```

Current hardware confirmed on 23 October 2026: 16-pin 16x2 parallel LCD, driven by LiquidCrystal on GPIO8-13. Use the current firmware README for wiring. Historical TFT/OLED sketch folders have been deleted. Do not recreate or use their display setup. `system_test/` is a separate diagnostic sketch. The root README now describes Wi-Fi synchronization in the current firmware.

Backend source files that define compatibility include:

```text
backend/app/api/deps.py
backend/app/api/v1/endpoints/devices.py
backend/app/api/v1/endpoints/sessions.py
backend/app/api/v1/endpoints/patients.py
backend/app/api/v1/endpoints/thresholds.py
backend/app/schemas/resources.py
backend/app/schemas/common.py
backend/app/models/entities.py
backend/app/core/config.py
backend/app/services/alerts.py
backend/tests/test_contracts.py
backend/tests/test_device_runtime.py
backend/tests/test_postgres_integration.py
firmware/tests/measurement_test.cpp
```

The documented hosted locations are:

- Dashboard: `https://neoguard-ai-lovat.vercel.app`
- Backend origin: `https://neoguard-api-wwth.onrender.com`
- Firmware API base: `https://neoguard-api-wwth.onrender.com/api/v1`
- Health: `https://neoguard-api-wwth.onrender.com/health`

These are documented addresses, not a claim that the service is currently reachable or running the latest local source. Deployment notes record an older cloud release, while newer firmware/runtime/frontend changes were prepared locally. Check compatibility explicitly. The hosted Render service may take time to wake; handle temporary unavailability without stopping acquisition.

For local testing, the laptop's `127.0.0.1` is not the ESP32's backend address. Document the reachable network address and server bind/configuration needed if using a local backend. Keep the dashboard, registered device secret, patient/session records and firmware API URL on the same backend/database.

## 2. Complete configured GPIO and connection map

The current target is an ESP32-S3. Exact development-board/module variant, flash size and PSRAM settings have not been established by this handoff. Preserve the known working board settings; identify any setting that must be confirmed. Native USB serial uses **115200 baud** with **USB CDC On Boot enabled**.

This table records the current source's intended wiring. It is not a physical continuity-test certificate.

| Module / signal | ESP32-S3 connection | Details |
|---|---|---|
| MAX30102 SDA | GPIO4 | Shared I2C data bus |
| MAX30102 SCL | GPIO5 | Shared I2C clock bus |
| MAX30102 INT | Unassigned | Current code polls the FIFO; do not invent an interrupt wire |
| MLX90614 SDA | GPIO4 | Same I2C bus |
| MLX90614 SCL | GPIO5 | Same I2C bus |
| DS1302 CLK / SCLK | GPIO6 | Three-wire RTC clock |
| DS1302 DAT / IO | GPIO7 | Bidirectional RTC data |
| DS1302 RST / CE | GPIO14 | RTC chip enable; not the display reset |
| ST7789 RST / RES | GPIO8 | Display reset |
| ST7789 DC / A0 | GPIO9 | Display data/command |
| ST7789 CS | GPIO10 | Current source uses chip select |
| ST7789 SDA / DIN / MOSI | GPIO11 | SPI data; a TFT pin labelled SDA is not necessarily I2C |
| ST7789 SCL / CLK / SCK | GPIO12 | SPI clock |
| ST7789 MISO | Unused | Current display connection has no readback |
| ST7789 BL / BLK / LED | Not established | No software backlight GPIO is configured; document the actual module requirement, do not invent a pin |
| Buzzer control | GPIO15 | Existing transistor-driven circuit, active-high default |
| RGB red channel | GPIO16 | Common-cathode default in code |
| RGB green channel | GPIO17 | Available but not normally used by current status logic |
| RGB blue channel | GPIO18 | Acquisition/running indicator |
| microSD CS | GPIO21 | Dedicated SD SPI bus |
| microSD SCK / CLK | GPIO40 | Dedicated SD SPI bus |
| microSD MOSI / DI | GPIO41 | Dedicated SD SPI bus |
| microSD MISO / DO | GPIO42 | Dedicated SD SPI bus |
| Optional SSD1306 SDA | GPIO4 | Only if the physical display is actually confirmed as this OLED |
| Optional SSD1306 SCL | GPIO5 | Shared I2C; not used by the default ST7789 branch |
| All module GND pins | Common GND | ESP32, modules and external breadboard supply share ground |

Bus/device settings:

- MAX30102: expected I2C address **0x57**; SparkFun's library uses the `MAX30105` class for this device.
- MLX90614: current code initializes **0x5A**.
- Shared I2C: currently **100 kHz**, SDA4/SCL5, finite bus timeout. Include a diagnostic scan.
- DS1302: **three-wire**, not an I2C DS3231/DS1307. It will not appear in an I2C scan.
- Default ST7789: **240 x 280**, **SPI mode 0**, **rotation 0**, currently **1 MHz** to match the successful isolated test.
- Optional SSD1306: **128 x 64**, address **0x3C** by default; **0x3D** is a module-dependent alternative. Only select this driver with evidence of that hardware.
- SD: independent SPI peripheral, mount at **1 MHz**, retry at **400 kHz**, existing FAT32 card.

Power details are incomplete. Use the established compatible supply for each sensor and the previously working display supply; confirm module specifications before changing voltages. The RTC guide specifies **3.3 V** for its DS1302 module. SD supply depends on the actual breakout: a regulator-equipped module may require 5 V at its input, while a native 3.3 V breakout requires 3.3 V. ESP32 GPIO signals and I2C pull-ups use 3.3 V logic; a 5 V sensor variant may require level translation. Do not infer module voltage from its colour. Check split breadboard rails and voltage at the module. Do not join an external regulated positive rail to USB-powered ESP32 power outputs.

The older wiring guide specifies **220-330 ohms per RGB channel**, common cathode to GND; for a common-anode LED, common goes to 3V3 and polarity changes in software. These are external LED channels, not the board's addressable onboard RGB. Its documented two-pin buzzer circuit is GPIO15 through **1 kohm** to an NPN base, emitter to GND, collector to buzzer negative, buzzer positive to its rated supply, and **10 kohms** from base to GND. It gives a 2N2222 as an example, with actual transistor pinout to be checked; an inductive buzzer needs an appropriate flyback diode, cathode toward buzzer positive. A three-pin buzzer module with its own driver instead uses IN/S to GPIO15, shared GND and rated VCC. Treat these as documented circuit recommendations; the actual fitted components/values and buzzer identity are unverified. Do not drive a two-pin buzzer directly from a GPIO.

There is no confirmed battery-measurement ADC, button, software backlight GPIO or complete power budget. Do not fabricate them. Backlight BL/BLK may be tied to 3V3 only when that module supports it; a bare LED backlight can require its own driver/current limiting. A genuinely CS-less TFT may use `TFT_CS=-1` only after confirming that interface. Do not leave an old parallel 16x2 LCD connected: its GPIO8-13 overlap the current TFT wiring. The recorded RTC cell is a non-rechargeable CR2032: keep the DS1302 trickle charger disabled.

## 3. The display failure must be investigated

I have called the screen an OLED in conversation, but the recorded working screen configuration is **ST7789 SPI TFT, 240 x 280**, selected by `DISPLAY_KIND 1`. Do not switch to SSD1306 solely because of my terminology.

Recorded evidence:

- `display_check` showed text and an increasing counter on the actual screen.
- Integrated firmware remained blank, including after its transfer speed was reduced to match the 1 MHz test.
- The latest D3 revision starts the display before LEDs, I2C and the SD SPI bus, then draws numbered white startup pages and prints `NEOGUARD FULL FIRMWARE D3 - screen-first startup`.
- D3 has a recorded selected-branch syntax check. Earlier revisions have complete build records. D3 has no recorded full link/upload/assembled-device verification. Do not present earlier build results as proof for your new code.
- `displayOK = true` only means initialization commands were sent. This SPI wiring has no physical screen readback.

Investigate pin ownership, CS/reset/backlight assumptions, SPI object lifetime and host assignment, initialization order, bus speed/mode, task ownership, memory/stack failures, watchdog resets and power behaviour. Add useful boot-stage diagnostics and a visible heartbeat/counter so we can locate the failure.

The current code uses global `SPI` for the TFT and `SPIClass sdSPI(HSPI)` for SD. An audit of the installed ESP32 Arduino **3.3.12** S3 environment found global `SPI(FSPI)` and `HSPI` are distinct peripherals. Do not assert a bus-host collision without checking the actual target/core definitions. If changing SPI ownership, explain the evidence and preserve the external pin map.

Keep display rendering in one owner task/context. Prevent SD, network or sensor code from reinitializing its bus/pins. Start with the confirmed screen-test sequence, then integrate each subsystem without abandoning the complete final firmware. Boot delays for diagnosis are acceptable; normal acquisition and alarm service must stay responsive. Support explicit build-time peripheral disable switches for isolation.

The final main display should show HR with bpm, SpO2 with %, **surface** temperature with C, date/time, acquisition/countdown or signal status, alarm/fault status, SD logging status, Wi-Fi/backend/session/sync status and useful setup instructions. Withhold invalid/stale numbers as `--` or a clear status. Retain the existing icon data where practical. Phone setup must show AP name, AP password and `192.168.4.1` together, with alarm/fault status still visible.

## 4. Sensor acquisition and measurement rules

Keep real sensor data only. No random values, fabricated readings, arbitrary calibration offsets or clamping values to make them look normal.

Current MAX configuration is:

```cpp
pulse.setup(60, 4, 2, 100, 411, 4096);
// LED brightness 60; averaging 4; red+IR mode 2;
// configured sample rate 100 Hz; pulse width 411 us; ADC range 4096.
```

The current firmware treats this as an effective FIFO output of 25 Hz and uses SparkFun's `maxim_heart_rate_and_oxygen_saturation` algorithm with a 100-sample red/IR window, recomputed after 25 new samples. Verify the rate/window assumptions against the actual installed library rather than copying an incompatible example. Use finite FIFO-drain work and handle overflow/service gaps explicitly.

- Contact gate: **IR >= 50000**, a provisional bench tuning value.
- Current algorithm-valid HR gate: **> 0 and <= 250 bpm**, additionally requiring the algorithm validity flag.
- Current algorithm-valid SpO2 gate: **0 through 100%**, additionally requiring the algorithm validity flag.
- Current temperature operating-range checks: finite object temperature **-70 through 380 C**, ambient **-40 through 125 C**. These broad existing gates are not medical normal ranges or accuracy proof.
- Loss of optical samples for over **2 seconds** is a fault/stale condition. Current code resets the pulse window on a FIFO-service gap of **120 ms** or more. Audit whether the implementation actually detects all meaningful gaps and overflow.
- Dedicated current pulse task: approximately every **5 ms**, priority 3, core 1, 8192-byte stack. Treat these as existing implementation choices to validate, not guaranteed timing.
- I2C temperature reads and any optional OLED transfers must be coordinated with optical acquisition. Do not hold an I2C mutex while doing unrelated CPU-heavy work.

Preserve the current requested minute-long repeatability policy, or explain a concrete defect and justify a correction:

1. Observe approximately once per second during continuous contact.
2. Require at least **60 seconds** of acquisition, with **45 valid observations** in the last minute and **12 valid observations** in the latest 15-second tail.
3. Recent max-minus-min spread must be <= **12 bpm**, <= **3 SpO2 percentage points**, <= **0.4 C**.
4. Publish medians of the valid tail, updating approximately every **5 seconds**.
5. A result older than **2500 ms** without a fresh observation must not remain ready. Finger removal, signal loss or unstable values clear readiness.
6. Reset measurement history and relevant alarm state when the assigned session changes; do not reuse previous-patient samples.

Audit whether reused algorithm outputs are being counted as independent fresh observations, whether a median gets a misleading acquisition timestamp, and whether combined validity improperly hides a useful independent temperature reading or alarm. Keep timing/quality semantics explicit. Do not assume waiting 60 seconds creates an accurate measurement. Do not smooth away actual threshold breaches.

## 5. Exact existing threshold and indicator policy

These are source defaults; download active backend settings when supported and cache the last validated configuration for offline use. Show whether limits came from the server, a cache, or defaults.

| Parameter | Existing condition | Backend severity |
|---|---|---|
| Heart rate low | HR < 100 bpm | medium |
| Heart rate high | HR > 160 bpm | medium |
| SpO2 low | SpO2 < 90% | high |
| Temperature low | 36.0 <= surface C < 36.5 | medium |
| Temperature moderately low | 32.0 <= surface C < 36.0 | high |
| Temperature severely low | surface C < 32.0 | critical |

Backend keys are `hr_low:100`, `hr_high:160`, `spo2_low:90`, `temp_low:36.5`, `temp_moderate_low:36.0`, `temp_severe_low:32.0`.

There is **no configured upper-temperature alarm**. Do not invent one. Exact equality to 100/160 bpm, 90% or 36.5 C does not breach the respective strict comparison. Do not confuse the sensor plausibility gates, API ingestion ranges and alarm limits.

Current local behaviour to preserve/audit:

- Three consecutive valid approximately one-second breaches confirm a local threshold alarm, including during the minute-long acquisition period.
- Qualified displayed readings beyond a threshold also sustain the alarm.
- Three consecutive fully valid in-range observations clear the raw alarm; invalid values are not evidence of recovery.
- Finger removal currently clears contact-related threshold flags and shows placement guidance. Distinguish loss of monitoring from a recovered normal measurement; explain whether independently valid temperature alarms should continue.
- Alarm: **red indicator** plus repeating buzzer **250 ms on / 250 ms off**.
- Sensor fault: red plus a **250 ms pulse every 2 seconds**.
- Startup beep: approximately **150 ms**.
- Blue: acquisition/running with no currently detected threshold alarm or sensor fault. Blue does not prove patient health, successful logging or backend delivery.
- Default `ACTIVE_BUZZER=true`, `BUZZER_ACTIVE_LOW=false`, `RGB_COMMON_ANODE=false`. Keep polarity/type configurable and document actual circuit assumptions. A passive buzzer option can use a suitable tone.
- Clock, SD and network faults need their own truthful status and must not silently become a sensor/clinical alarm.
- Current local CSV alarm bits are 1=HR low, 2=HR high, 4=temperature low, 8=SpO2 low. Keep that encoding documented if retained; it is not an accepted API reading field.

The backend evaluates vital thresholds only for `quality:"ok"`. Other allowed quality states generate a quality/device-error rule instead. Local alarms and backend alerts are separate behaviours: explain their timing and differences, especially for withheld or partial data. There is currently no API field for arbitrary on-device alarm flags; do not invent one in a strict payload.

## 6. Exact backend device contract

Use **HTTPS REST**, not MQTT or direct database access. Firmware uses a **per-device secret** issued by the device registry:

```http
Authorization: Bearer <DEVICE_SECRET>
Content-Type: application/json
```

This is not a dashboard login password and not a staff JWT. Device credentials must be active and the registered device status must be `active`. Never print secrets, embed real credentials in delivered source, or ask me to paste them into a shared prompt. Configure them through the local phone portal.

### A. Assignment, thresholds and time

Preferred: `GET /api/v1/devices/runtime` with device authentication.

Response shape:

```json
{
  "device_code": "NG_DEVICE_001",
  "session_id": 123,
  "session_started_unix": 0,
  "server_time_unix": 0,
  "thresholds": {
    "hr_low": 100,
    "hr_high": 160,
    "spo2_low": 90,
    "temp_low": 36.5,
    "temp_moderate_low": 36.0,
    "temp_severe_low": 32.0
  },
  "threshold_provenance": {}
}
```

The zeros above illustrate numeric types only; actual server responses contain actual UTC Unix seconds. Never hard-code or use those zeros as real time. The numeric session ID is an example, not an assignment. With no active session, both `session_id` and `session_started_unix` are `null`. Provenance may include threshold ID, value, unit, version, source, description and effective time.

Legacy: `GET /api/v1/devices/current-session`, same device authentication:

```json
{"device_code":"NG_DEVICE_001","session_id":123}
```

It returns `session_id:null` if unassigned. It does not supply active limits, session start time or server time. Fall back carefully when `/runtime` is absent on an older deployment. Old routing may match `runtime` as a dynamic device ID and yield an auth/validation error instead of 404; the current compatibility helper allows legacy discovery after 4xx except 429. Check the legacy result using the same credential; do not treat real authorization failures as successful provisioning, bypass throttling, or pretend legacy limits were downloaded. Do not fall back merely because of a TLS failure, timeout or server 5xx.

Poll assignment approximately every **10 seconds**. Show `NO ACTIVE SESSION` when appropriate. With no assignment, continue bench acquisition/display/local alarms/CSV, but do not attach readings to a guessed patient. Cache session identity only for its original device and clearly show when offline assignment is unconfirmed. Reset new-patient measurement history on a change. Existing queued old-session events retain their old session.

### B. Readings and telemetry

`POST /api/v1/devices/sync` with device authentication.

Example schema-valid body for one event:

```json
{
  "device_code": "NG_DEVICE_001",
  "firmware_version": "neoguard-integrated-1",
  "readings": [
    {
      "session_id": 123,
      "event_id": "6eb9fdc7-44bd-4c35-91b1-275b330e356a",
      "measured_at": "2026-10-20T12:00:00+03:00",
      "heart_rate_bpm": 140,
      "spo2_percent": 97,
      "temperature_c": 36.8,
      "quality": "ok"
    }
  ],
  "telemetry": {
    "reported_at": "2026-10-20T12:00:00+03:00",
    "wifi_rssi_dbm": -65,
    "uptime_seconds": 3600
  }
}
```

All IDs, values and dates above are illustrative. Generate real unique event IDs and actual acquisition timestamps, and discover a real assigned session. The sample is not suitable for replay into an arbitrary active session.

Strict requirements:

- Top-level fields only: `device_code` (3-30 chars), optional `firmware_version` (max 30 chars), `readings` (up to 500), optional `telemetry`, optional `component_checks` (up to 100).
- Every reading requires a positive integer `session_id`, a UUID `event_id`, and timezone-aware `measured_at`.
- At least one non-null vital: integer `heart_rate_bpm` **40-220**, integer `spo2_percent` **50-100**, finite numeric `temperature_c` **30-42**.
- `quality` is exactly `ok`, `poor`, `motion_artifact` or `sensor_error`; default is `ok`. Mark quality honestly. Current firmware uses `poor` for partial events.
- All input models forbid extra fields. Do not send `patient_id`, `patient_code`, top-level `session_id`, raw IR/red values, alarm flags, custom quality strings, or fabricated battery readings.
- Optional telemetry: timezone-aware `reported_at`; optional integer `battery_percent` 0-100, integer `wifi_rssi_dbm` -127 through 0, nonnegative integer `uptime_seconds`. Omit battery percent because no actual measurement circuit is established.
- Optional component checks: `component_type` (2-50 characters), timezone-aware `checked_at`, status from `ok|error|timeout|not_detected|drift_detected`, optional `error_code` max 50 chars and `details` object. A component type must already be registered for the device; otherwise the API rejects and rolls back the request. Omit component checks by default unless registration is verified.
- Out-of-API-range measured values remain available in raw CSV/diagnostics. Never clamp them into an accepted range. Send another genuinely valid available field with honest partial quality if appropriate; otherwise omit the event and report why.
- Use a heartbeat with `readings:[]` and truthful telemetry while warming up or unassigned. Heartbeats establish connectivity, not valid patient measurements.

Successful response shape:

```json
{
  "device_code": "NG_DEVICE_001",
  "received_at": "2026-10-20T09:00:01Z",
  "readings": [
    {
      "event_id": "6eb9fdc7-44bd-4c35-91b1-275b330e356a",
      "status": "accepted",
      "reading_id": 456,
      "reason": null
    }
  ]
}
```

Per-event statuses: `accepted`, `duplicate`, `rejected`. A rejected item may have `reading_id:null` and a reason. Match acknowledgements to device code and every original event UUID; missing, malformed or mismatched results are not success. **HTTP 200 alone does not prove the batch was stored.**

Idempotency and session rules:

- Event IDs are unique per device. Identical event UUID/session/timestamp/vitals/quality on retry returns `duplicate`.
- Reusing a UUID with changed content returns `rejected`.
- A session must belong to that authenticated device.
- Measurements more than **5 minutes in the future** are rejected.
- Measurements before the original session start or after its recorded end are rejected.
- Historical upload to a stopped/completed session is allowed when observation time was inside that session. Never rewrite old events to the latest session.
- `measured_at` is original observation time. `received_at` is server arrival time. Do not replace the original time with reconnect time.
- Schema-invalid data can reject the whole request with 422. Some semantically invalid events return per-item rejection in a 200 response. Handle both.

Rate/error handling:

- Default minimum gap between successful `/devices/sync` requests is **5 seconds per device**, shared by telemetry heartbeats and reading batches. Use approximately **6 seconds or more** between POST attempts and one common scheduler; honour **429 `Retry-After`** and any longer deployed limit.
- Existing target cadence: one eligible stable reading every **5 seconds**, batches up to **20 events**, heartbeat approximately **15 seconds** when it does not compete with a batch.
- Retry network/TLS/timeouts/5xx with bounded exponential backoff and jitter while preserving data. On 409 concurrency conflict, retry the unchanged batch.
- On 401/403, display a useful credential/inactive-device error and avoid a tight retry loop. Do not erase queued readings or leak the token.
- Parse bounded error bodies and per-item reasons for diagnostics.
- Support valid chunked or unknown-Content-Length HTTP responses. Current `backendRequest` reads a body only when `http.getSize() >= 0`, which can discard a legitimate response. Correct this with a bounded read/decode strategy; do not substitute unbounded memory consumption.

## 7. Offline storage and clock correctness

Preserve durable, immutable reading events on SD before attempting network delivery when SD is available. Current paths are:

- `/neoguard_v2.csv`: approximately one row per second, with raw and stabilized measurements, validity/contact information, time, alarm flags and boot/row identity.
- `/pending.ndjson`: serialized upload events with original UUID, original session and original measurement time.
- `/sync.cursor`: persistent replay progress.

Preserve old CSV files; never autoformat or erase a card. A durable cursor/checkpoint must not skip unacknowledged events. If power fails after server acceptance but before checkpoint persistence, resend the same immutable events and rely on duplicate recognition.

The existing implementation keeps a whole rejected batch at the head of the queue, which can block later valid events. Design a documented solution that durably retains rejected/corrupt records and reasons for inspection, allows later valid events to progress where safe, and never silently discards or rewrites them. Quarantine must be committed before advancing past an event. Account for mixed accepted/rejected batches, incomplete NDJSON writes, missing/damaged cursors, card-full and write failures, and SD I/O ownership. Explain any queue format migration; preserve old data. Do not claim lossless power-failure guarantees for FAT32.

If SD fails, keep local measurement/display/alarms running. The current fallback is **12 events in RAM**, which are lost on reboot; queue-full losses are counted visibly. Implement bounded memory use, a clear retention/loss status and a safe SD retry policy. Current SD remount attempts are spaced **10 seconds** apart while no finger is present to avoid disturbing acquisition. Manage capacity explicitly and avoid undocumented deletion or automatic formatting. Power down before card insertion/removal.

Time rules:

- DS1302 currently stores **Africa/Nairobi local time, UTC+03:00**.
- API timestamps must have `+03:00` or a correctly converted UTC `Z`; never mislabel local time as UTC.
- NTP/system time and authenticated runtime server time are UTC Unix seconds. Handle conversion exactly once, including the Makuna RTC epoch if using its conversion helpers.
- TLS certificate checks need valid system time. Bootstrap from a valid RTC or NTP; do not require a successful HTTPS call to obtain the only time source needed to establish that same HTTPS connection.
- Synchronize RTC from trusted network/server time when appropriate; do not continually overwrite a good RTC with compile time.
- Preserve `TIME?`, `TIME YYYY-MM-DD HH:MM:SS` (Nairobi) and `WIFI SETUP` serial commands. Parse and validate dates, buffer lengths and line endings.
- With an invalid clock, log explicit missing time and avoid queueing API events with fabricated dates. Do not retroactively attach unassigned CSV rows to a patient.
- Warn operationally that moving to another patient while offline cannot be detected automatically. Reconnect, stop/assign the intended session and confirm discovery before measuring the new patient.

## 8. Wi-Fi setup and task design

Keep phone provisioning with **WiFiManager by tzapu**:

- AP name `NeoGuard-XXXX`, unique locally generated saved AP password, setup URL `http://192.168.4.1`.
- Select a **2.4 GHz Wi-Fi** network; provide fields for registered device code, device secret, HTTPS API base.
- Save settings using Preferences/NVS. Blank secret retains the old secret only when device identity stays the same. Changing device identity invalidates cached assignment/limits and needs that device's credential; do not upload another device's old queue under the new identity.
- Show complete setup instructions on the screen and serial; do not log Wi-Fi passwords or device secrets. The AP setup password is deliberately shown locally so the user can connect.
- Keep acquisition and alarms running while the portal is open. After successful configuration, restart only after storage operations are safe, or apply validated settings safely.
- Reconnect automatically and permit `WIFI SETUP` to reopen provisioning. Make Wi-Fi connected, backend authenticated, session assigned and readings acknowledged distinct states.

Keep pulse acquisition independent of blocking HTTPS/TLS, captive-portal handling, display drawing and SD writes. Use explicit task ownership, bounded queues and synchronization. Current network work is priority 1, core 0 with a 16384-byte stack; assess stack/heap and scheduling instead of assuming these sizes suffice. Do not copy nontrivial C++ `String` objects by raw FreeRTOS queue byte copying; choose safe ownership and cleanup on every error path. Keep SD access in one owner. Consider OLED transfer time if that optional shared-I2C branch is retained. Use elapsed-time arithmetic safe across `millis()` rollover and avoid hot busy loops/watchdog starvation.

Add bounded sensor rediscovery/reinitialization after missing or failed MAX/MLX devices; current detection flags are set once at boot, so a recovered sensor can remain unavailable. Avoid resetting a healthy shared I2C bus repeatedly. Track Wi-Fi, backend authentication, assignment, pending uploads, SD, clock and measurement state separately: the current runtime poll can overwrite an upload failure with `SESSION CONNECTED`. If optional SSD1306 support is delivered, include a readable compact/paged view of countdown, alarm and session/queue states; the existing OLED normal layout omits some of those statuses.

Use authenticated TLS with the public CA in `root_ca.h` or a justified maintained trust store. Do not use `setInsecure()`, plain HTTP for deployed credentials, or automatic fallback to insecure transport. Certificate-chain/expiry changes must fail visibly and have an update procedure. The delivered code must not contain real passwords, secrets, database URLs or staff tokens.

## 9. Required complete deliverables

Produce the following in a clear order:

1. A concise evidence-based diagnosis of likely failure points and how your implementation addresses each. Say which root causes remain unconfirmed. List only hardware details that genuinely cannot be inferred and materially affect configuration.
2. A final wiring table with all connections above, power assumptions, I2C addresses, SPI host ownership and display selection. Flag unknown backlight/power details rather than inventing them.
3. A complete Arduino IDE-ready firmware folder, with a main `.ino` whose name matches the folder, all required `.h/.cpp` files, retained/generated icon definitions and public CA configuration. Provide full contents, no ellipses, missing functions, placeholders for core logic, or dependencies on files you have not supplied. Credentials are intentionally user-configured; these are the only kind of secret placeholders allowed. Prefer a small coherent module set over unnecessary fragmentation.
4. Exact library names, tested versions where known, ESP32 core version, board settings and installation/build/upload instructions. Existing dependencies are SparkFun MAX3010x, Adafruit MLX90614, Rtc by Makuna, Adafruit GFX, Adafruit ST7735 and ST7789, ArduinoJson **7**, WiFiManager **2.0.17**, and ESP32-provided Wire/SPI/SD/WiFi/Preferences/secure client libraries. SSD1306 support additionally needs Adafruit SSD1306. Compile every branch you claim is supported. If board flash/PSRAM details are unknown, state that instead of guessing.
5. Backend compatibility notes. Preserve the existing API and database model; provide a minimal backend patch only if strictly necessary, with reasons and migration/deployment steps. Do not silently require new endpoints or fields. Explain runtime discovery on both the new and legacy backend.
6. Setup steps: register/activate a device in the correct clinic, retain its one-time secret securely, create/select the patient, start a session, configure the device against the same backend, then confirm session discovery and acknowledged real readings. Administrator registry screens intentionally differ from nurse/clinician clinical views. The dashboard currently has some older component labels; those labels do not change the physical sensor/RTC hardware.
7. A focused verification plan and expected serial/display outputs. If you can compile or run tests, do so and provide actual results, toolchain and limitations. If you cannot, state precisely what remains untested; never invent a successful build, flash or live transfer.

Acceptance checks must cover:

- Visible boot text and advancing display counter, first in isolation and then with sensors, SD, Wi-Fi and sync simultaneously active.
- I2C detection, actual advancing FIFO samples and raw channels, placement guidance, qualification countdown, stable real results, immediate invalid/stale indication and honest surface-temperature labels.
- Alarm boundary equality, confirmed breaches/recovery, invalid-data handling, buzzer/RGB polarity, acquisition during alarms and during phone setup.
- RTC unset/correct time/reboot/timezone conversions; TLS operation with valid time and clear failure with an invalid clock or invalid trust.
- Fresh assignment, no session, session change/reset, cached offline assignment, and stopping a session without assigning historical data to a new patient.
- Valid authenticated sync, heartbeat-only sync, unchanged retry/duplicate handling, mixed rejection, 401/403, 409, 422, 429 with Retry-After, timeouts, 5xx and chunked/unknown-length replies.
- Offline acquisition, reboot with pending SD data, reconnect replay to original sessions, power interruption around acknowledgement/checkpoint, damaged queue/cursor, full/missing/failed SD, and explicit RAM-loss accounting.
- Real readings visible in nurse/clinician dashboard history with correct measured versus received timestamps and no fabricated points; backend threshold alerts remain independent of research AI availability.

Use synthetic fixtures only in clearly separated software tests and controlled bench inputs for alarms; never feed test data into an unsuspecting live patient session. Do not request a real-patient test. Summarize actual measured hardware limitations when they are known.

Finish with exactly what I must configure, upload and observe to verify the complete sensor-to-device-to-backend-to-dashboard flow. If information is missing, proceed with the evidence-based default configuration above and clearly isolate the uncertainty. Ask only essential questions that block a real implementation. My priority is complete integration, a visibly functioning display, truthful measurements/status and reliable backend communication.
