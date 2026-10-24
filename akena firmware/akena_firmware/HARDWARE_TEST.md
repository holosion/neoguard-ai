# Heart-rate averaging and LED ranges -- 24 October 2026

**Current firmware: `akena-st7789-6`, compiled and uploaded successfully.**
The user confirmed that the new average is smoother and clears after removal.
The reported blue LED at a displayed 125 was traced to the separate qualification
gate, rather than an out-of-range average. The LED policy is now separate from
AI qualification. The user confirmed green with `IN RANGE / ESTIMATE` in the
short retest, and the serial recording corroborated the green output. The earlier
backend/UI test below also passed.

- Display HR is the mean of distinct valid estimates in a rolling 10-second
  window, published every three seconds. Five estimates spanning four seconds
  are required; initial MAX acquisition adds approximately four seconds.
- Removal, invalid current data or a stale estimate clears availability. A long
  signal gap resets history. Repeated snapshots do not inflate the sample count.
- Smoothing affects the OLED-style ST7789 display only. Raw alarm inputs, CSV,
  backend uploads and full stability qualification remain unchanged.
- Green requires a ready average plus fresh, valid displayed values inside all
  current limits: HR 100--160, SpO2 >=90, surface >=32 C, with no confirmed alarm
  or sensor fault. Until full qualification passes, the screen says
  `IN RANGE / ESTIMATE`. Blue means averaging, unavailable data or pending limit
  confirmation. Red retains priority for faults and confirmed raw-reading alarms.
  Green does not establish that a person is well or promote AI eligibility.
- Averaging cannot promote poor-quality readings into AI-eligible measurements.
  The existing experimental backend model is separate from local RGB/buzzer rules.

Compile/link PASS: 1274277 / 1310720 program bytes, 52136 static RAM bytes.
36443 application bytes remain. COM7 upload PASS, flash hash verified.
Binary SHA256: `F7B77672128243B36E557AFD546454480B1C17BE2B227E7F70B44D4A2F1E6ECC`.
New boot `94033BC8` reconnected to Wi-Fi/session 1 with RTC=SD=MAX=MLX=1,
runtime_http=200, heartbeat_http=200, TLS_error=0. The hosted device reports
`akena-st7789-6`. No-contact display/LED status was unavailable HR / blue.

Host checks PASS: rolling average cadence/window, distinct estimates, startup,
invalid/stale/removal handling, sustained changes, uptime rollover and indicator
priority/boundaries. Existing measurement/alarm and live-vitals regressions PASS.
Tests cover green for fresh in-range display estimates without changing quality,
blue for missing/stale readings, inclusive boundaries and red alarm/fault priority.
The physical retest passed: the user saw green with `IN RANGE / ESTIMATE`.
The new capture recorded four green snapshots, including averaged HR 119.0 bpm,
oxygen estimate 100%, surface 34.13--34.23 C and no active alarm. Qualification
remained false, confirming the LED did not promote AI eligibility. After removal,
the average cleared and LED returned to blue. Raw-reading alarms also retained
red priority during the run. Runtime/heartbeat/sync returned HTTP 200; the durable
cursor advanced from 10955 to 12040. Final SD LOGCHECK passed at row 230, with
sampler_resets=0, temperature_packet_errors=0 and queue_damaged=0. Serial was closed
after recording; the board remains running. Analysis:
`.local/neoguard-led-range-analysis.json`.

The preceding firmware-5 `8B7697B4` capture contained 109 contact snapshots and 82 available
averages; none passed full qualification. Around displayed 125.4 bpm, raw HR
spanned 100--136 bpm over the recent window, oxygen was 100%, and surface was
34.07--34.29 C. The contact timer at that point was 13--16 seconds; its longest
detected uninterrupted stretch in the run was 44 seconds. This explains the old
blue policy (60 seconds and raw HR spread <=12 required). The user confirmed the
display smoothing/removal behavior. Final SD LOGCHECK passed at row 588;
runtime/heartbeat/sync remained HTTP 200, cursor reached 10955, sampler resets and
temperature packet errors remained zero. Analysis: `.local/neoguard-average-analysis.json`.

Current evidence: `.local/neoguard-led-range-build.log`,
`.local/neoguard-led-range-upload.log`, `.local/neoguard-led-range-live.log`,
`.local/neoguard-led-range-backend.json`, `firmware/tests/heart_average_test.cpp`.
The preceding `.local/neoguard-average-*` evidence retains the smoothing test and
original blue-at-125 observation. Pre-change source backups are under
`.local/firmware-backups/pre-average-20261024/` and
`.local/firmware-backups/pre-led-range-20261024/`. The firmware and AI READMEs
explain the averaging, separate qualification and experimental model flow.

---

# Preceding backend integration validation -- 24 October 2026

**Current result: final firmware uploaded; authenticated ESP32 delivery and the
hosted web app's API connection verified.** Physical screen checks passed by user
observation. The user completed the final finger/warm-hand test and confirmed
that heart rate, oxygen and surface temperature all appeared in the hosted CASE
nurse view for BENCH-E1E078.

## Current build and registration

- Target: `esp32:esp32:esp32s3:CDCOnBoot=cdc`, ESP32 core 3.3.12.
- Firmware identifier: `akena-st7789-4`.
- Program: 1272745 bytes of 1310720; 37975 bytes remain. Static RAM: 52016 bytes.
- Upload: COM7, MAC `24:58:7c:e1:e0:78`; flash hashes verified.
- Binary SHA256: `DA95FD050C9EB37E3634D3F106D985BFCA5B34501D8FCC595E081D11574D39A4`.
- Existing wiring and saved Wi-Fi credentials were retained.
- Registered board: `NG-E1E078`, device 1, CASE clinic 2.
- Clearly labelled bench record: `BENCH-E1E078`, patient 1, active session 1.
  No invented patient demographics or artificial readings were submitted.
- Device secret is private configuration; it is not embedded in source or reports.

## Fixes and evidence

1. **Wi-Fi association did not provide a usable DNS resolver.** The board's own
   setup page reported station IP 192.168.137.246, gateway 192.168.137.1 and DNS
   0.0.0.0. Backend calls returned HTTP -1. The gateway DNS check also failed,
   while 1.1.1.1 resolved the backend. Firmware now fills missing DNS using an
   existing secondary resolver or 1.1.1.1/8.8.8.8, preserving supplied primary DNS
   and DHCP addressing. The subsequent ESP32 HTTPS runtime/heartbeat calls passed.
2. **Successful chunked responses were discarded.** The authenticated backend
   returns HTTP 200, Transfer-Encoding chunked, no Content-Length, and a 1764-byte
   runtime body containing session 1. The old nonnegative-size check skipped that
   body, leaving the board at session 0. The bounded streaming reader now decodes
   chunked replies, caps bodies at 20000 bytes, and rejects incomplete reads. The
   final board obtained session 1 and processed actual upload acknowledgements.
3. **Pulse display depended on every sensor passing a minute-long gate.** Fresh
   algorithm-valid HR and SpO2 estimates now appear independently, while the
   original full qualification check remains separate. Missing/stale values are
   unavailable, never zero-filled or clamped. Unqualified upload packets carry
   poor quality; qualified medians carry ok quality. The user confirmed both
   numbers appeared and cleared on finger removal; serial capture corroborated it.
4. **Surface low-temperature limit was too high for this bench setup.** The local
   low limit is strictly below 32 C, with independent per-parameter confirmation
   and recovery. Server clinical defaults no longer overwrite that local surface
   setting. The user confirmed no temperature-low alarm at 32 C or above. Host
   tests covered equality at 32 C and recovery while pulse values are unavailable.

HTTPS certificate and hostname checks remain enabled. The CA list contains
GlobalSign Root CA and the official Google Trust Services Root R4. Certificate
checks were never disabled to make the network test pass.

## Final physical and hosted checks

| Check | Actual result |
|---|---|
| Final boot | `4D5545F6`; dashboard mode, Wi-Fi connected, IP 192.168.137.246 |
| Components | RTC=1, SD=1, MAX=1, MLX=1 |
| Backend context | configured=1, session=1, runtime_http=200 |
| Heartbeat | heartbeat_http=200; hosted device status online |
| Reading delivery | sync_http=200; eight acknowledged batches in the captured run |
| Durable upload progress | SD cursor advanced from 0 to 2400 in capture, then 4051 at final reader-closed recheck; queue_damaged=0 |
| Backend storage | latest_reading_at advanced to 2026-10-24 22:15:25 +03:00 at final hosted-app check |
| Hosted frontend API | Authenticated request through its own /api/v1 proxy saw the same latest reading and online device |
| Hosted nurse view | User confirmed all three values appeared in BENCH-E1E078 during the final physical test |
| Pulse removal | HR_available=0 and SpO2_available=0 after removal |
| Acquisition | Final recheck sample count 8336; sampler_resets=0 |
| MLX packet integrity | temperature_packet_errors=0 |
| SD readback | LOGCHECK PASS at row 202 and at row 298 after the reader-closed interval; same boot |
| Firmware tests | Measurement/alarm and live-vitals host regressions passed |
| Frontend checks | Three display tests and production build passed |

The hosted update is READY at https://neoguard-ai-lovat.vercel.app, deployment
`dpl_8CX7ad6cUvk5YoWGZeZvvQUH94ti`. Its public bundle contains the surface and live
estimate labels. The bench view preserves each recent metric across partial
packets, expires values after 15 seconds, and distinguishes estimates from
qualified readings. Non-bench clinical display thresholds remain unchanged.
Clinical readings are viewed with the CASE nurse account; the existing admin
role shows operational device information and does not expose patient vitals.

Occasional sync_http=-100 during the run was the local six-second upload cooldown;
the batch was retained and then acknowledged. It did not indicate data loss.

## Remaining flaws and limits

- Pulse estimates remain unstable. The earlier contact run had valid algorithm
  reports ranging from 46 to 150 bpm; the final run also produced an out-of-range
  37 bpm estimate, which was omitted rather than clamped. No captured run passed
  full stability qualification. Seeing values and delivering them is not proof
  of accurate HR/SpO2; they remain explicitly labelled estimates.
- HR limits remain 100--160 bpm and oxygen low limit remains 90%. An adult bench
  finger can still trigger the HR alarm even when surface temperature is above
  32 C. The buzzer is driven by any confirmed active parameter alarm.
- The 32 C change is for the physical surface sensor and bench display. Global
  clinical backend thresholds were not changed. MLX90614 measures surface, not
  core temperature.
- The prior intermittent SD mount fault recovered after physical checks/retries;
  its underlying hardware cause, long-term reliability and RTC battery retention
  remain unverified. Application flash has only 37975 bytes of spare space.

Current evidence, relative to repository root:

- `.local/neoguard-backend-response-build.log` and `...-response-upload.log`.
- `.local/neoguard-backend-final-live.log` -- actual values, removal, HTTP results,
  eight acknowledgements, saved cursor and SD readback.
- `.local/neoguard-backend-live.log` -- earlier physical display/alarm test and
  pre-fix HTTP -1 failures.
- `.local/neoguard-board-network-info.html` -- original missing DNS observation.
- `.local/neoguard-runtime-http-format.json` -- actual chunked runtime response.
- `.local/neoguard-backend-dns-live.log` -- DNS fix restored HTTP 200 but old reader
  still left session 0.
- `.local/neoguard-backend-delivery-verified.json` and
  `.local/neoguard-final-frontend-api.json` -- stored-reading and web proxy checks.
- `.local/neoguard-backend-headless-final.log` -- final reader-closed continuity,
  HTTP 200 outcomes, saved cursor 4051, SD readback at row 298; serial left closed.
- `.local/neoguard-hosted-ui-verification.json` -- public bundle/deployment check.
- `.local/firmware-backups/pre-backend-fixes-20261024/` -- pre-change firmware.

---

# Historical Wi-Fi-only validation -- 24 October 2026, before backend provisioning

**Status: final Wi-Fi firmware uploaded; local monitoring/logging checks passed.**

The ESP32-S3 is connected to Wi-Fi at **192.168.137.232**, with setup closed and
normal dashboard mode restored. Serial was closed at the end. Backend registration
is still required before authenticated data delivery can be tested.

The current build combines the ST7789 240x280 screen, MLX90614, MAX30102, DS1302,
RGB, buzzer and SD logging with Wi-Fi provisioning and HTTPS syncing support.
The preceding offline source is backed up in
`.local/firmware-backups/pre-wifi-20261024/`.

## Final firmware checks

| Check | Actual result |
|---|---|
| Compile/link | PASS; ESP32 core 3.3.12, CDC-on-boot target |
| Size | 1269481 bytes program, 51992 bytes static RAM; fits default application partition |
| Flash | PASS; COM7, ESP32-S3 MAC 24:58:7c:e1:e0:78; flash hashes verified |
| Saved Wi-Fi reconnect | PASS after final upload/reset; 192.168.137.232, RSSI -35 to -37 dBm |
| Dashboard mode | Initial/final portal=0 despite missing backend credentials |
| Phone setup | WIFI SETUP opened portal=1 while station stayed connected |
| Local web page | Setup root and exit route returned HTTP 200 |
| SD | Final boot mounted successfully; repeated exact latest-row readbacks passed |
| Reader-closed logging | PASS; reader closed for 25 seconds, same boot continued |
| Reporting rate | 39 CSV-row increments / 39.020 seconds spanning the test; 0.999 rows/sec |
| Final SD readback | LOGCHECK PASS at saved row 110; later CSV rows continued |
| Pulse acquisition | Final snapshots sampler_resets=0 with Wi-Fi, display and SD active |
| Temperature packets | Final snapshots temperature_packet_errors=0 |
| RTC | Correct advancing Nairobi time; final command returned 2026-10-24 21:02:56 |
| Backend registration | configured=0, session=0; no saved device code/secret |
| ESP32 backend requests | runtime_http=0, heartbeat_http=0, sync_http=0; not attempted |
| Backend reachability from PC | Public /health returned HTTP 200, NeoGuard Backend healthy |

The final timed test used boot ID `7FBECEB3`. Its rate spans the closed-reader
interval plus surrounding capture/readback commands, rather than claiming 39 rows
were written during only the 25-second closure. Exact SD readbacks passed on both
sides. The setup screen stayed active during this test, exercising the corrected
redraw behavior. It was then closed through its exit route; final STATUS confirmed
Wi-Fi connected, portal=0, RTC=1, SD=1, MAX=1 and MLX=1.

## Wi-Fi and backend behavior

Wi-Fi settings are saved through the password-protected phone portal. Both device
fields may remain blank for Wi-Fi-only operation. A successful station reconnect
does not force the setup screen open just because backend registration is missing.
WIFI SETUP can reopen the device fields later. The normal dashboard remains usable.

STATUS exposes Wi-Fi/IP, device session, HTTP outcomes, sampling counters and
upload progress without printing Wi-Fi passwords or device secrets. The backend
firmware identifier is `akena-st7789-3`. HTTPS requests and queued-reading delivery
require the correct device code/secret; readings additionally require an active
monitoring session and valid qualified measurements. No artificial readings were
created to test delivery. No authenticated ESP32/backend test is claimed here.

The public backend health check succeeded from the PC. That is separate from
ESP32 internet/TLS/authentication. Backend provisioning and data delivery remain
untested; the present device is configured only for Wi-Fi and local monitoring.

## Faults found and handling

1. **SD mount failed on the initial Wi-Fi boot.** Normal 1 MHz and 400 kHz attempts
   failed, including SD RETRY and an isolation test with sampling paused/I2C
   released. The user reported checking/reseating the card/wiring and reconnecting.
   Subsequent retries recovered the card. The final firmware boot mounted it and
   passed repeated write/readback checks. The precise failure cause was not
   isolated; no formatting or deletion of existing files occurred.
2. **Setup-screen redraws slowed reporting.** With SD working, the earlier timed
   test produced only 0.765 reports/sec. Full setup-page redraws were repeated
   every few seconds. Setup details now draw once on entry; only the status band
   changes when needed. The final reader-closed test passed at 0.999 rows/sec.
3. **RTC initially reported year 2090.** Verified serial time setting corrected it
   to current Nairobi time. It remained correct through the final firmware reset.
   The cause of the incorrect year and battery retention through complete power
   loss remain unverified. clock_ready=1 alone is not proof of accurate NTP time.
4. **Wi-Fi previously depended on backend setup for its screen flow.** Missing
   device credentials could reopen the portal after a station reconnect. Wi-Fi
   now works independently and STATUS reports DEVICE SETUP NEEDED, leaving the
   dashboard available. User Wi-Fi settings survived the final firmware upload.
5. **Application space is nearly full.** The build fits with 41239 bytes remaining
   in the default application partition. Larger future features may require
   reviewing the partition layout.

The earlier integrated SD SPI end/rebind correction remains in place. Earlier USB
output could block reporting without a reader; this build uses nonblocking USB
output and independent SD appends. The final timed test passed with serial closed.
An earlier USB disappearance had no captured panic/brownout trace; its cause was
not established. The board was reconnected and flashed successfully afterward.

## Previously confirmed offline workflow

The user confirmed the dashboard/UI works, qualified HR/SpO2 appeared after the
requested steady-contact test, and values cleared on removal. The user confirmed
red RGB and pulsing buzzer during a threshold alarm. These physical observations
refer to the preceding offline validation; they are distinguished from captured
qualified-reading rows on the final Wi-Fi build.

The corrected offline run also mounted SD, captured 51 complete CSV rows and passed
three exact latest-row readbacks. Native measurement/alarm and MLX packet checks
passed. The measurement qualification and alarm algorithms were not changed by
this Wi-Fi addition; no thresholds were weakened to force a successful result.

Medical accuracy/calibration, long-term card reliability, RTC battery retention
and authenticated backend delivery have not been established by these checks.

## Evidence

Paths are relative to the repository root:

- `.local/neoguard-wifi-build.log` -- latest successful compile.
- `.local/neoguard-wifi-upload.log` -- verified upload of the final source.
- `.local/neoguard-wifi-final-validation.log` -- reconnect, setup-mode and timed SD PASS.
- `.local/neoguard-wifi-dashboard-final.log` -- final connected/dashboard/readback state.
- `.local/neoguard-wifi-portal-http.json` -- local setup and exit HTTP outcomes.
- `.local/neoguard-wifi-joined.log` -- Wi-Fi connected after the user's setup.
- `.local/neoguard-wifi-headless-recheck.log` -- earlier 0.765/sec redraw-rate failure.
- `.local/neoguard-wifi-hardware.log` -- first boot's failed SD/rate checks.
- `.local/neoguard-wifi-storage.log` -- normal/quiet SD retries and RTC correction.
- `.local/neoguard-integrated-bus-diagnostic.log` -- preceding offline integration.
