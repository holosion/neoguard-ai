# Hardware test -- 24 October 2026

**Result: partial pass.** The sketch is uploaded and running on the attached ESP32-S3
on COM7. It communicates with both sensors and the display/buzzer command path works.
Reliable heart-rate measurement and audible automatic interaction beeps are not established.

## What was verified

| Check | Result and evidence |
|---|---|
| Compile/link | Passed for `esp32:esp32:esp32s3:CDCOnBoot=cdc`; 345966 bytes flash, 24912 bytes static RAM |
| Upload | Passed; esptool identified ESP32-S3 rev 0.2 and verified written flash hashes |
| Display | User confirmed colour bars/text visible; D command was received and executed |
| Buzzer commands | User confirmed audible beeps; B command was received and executed |
| I2C | GPIO4 SDA and GPIO5 SCL idle high; addresses 0x57 and 0x5A both responded, zero scan bus errors |
| MLX90614 | Returned changing surface and ambient readings; surface 25.97--30.73 C across the two captures |
| MAX30102 raw input | Fresh red/IR samples; finger IR 91561--105770 versus about 700 when uncovered |
| Finger detection | One `EVENT: Oximeter: finger detected` was logged; contact became false after removal |
| Estimate clearing | HR/SpO2 returned to `--` with finger removal and window reset to 0/100 |
| HR/SpO2 calculations | HR 42--187 bpm, SpO2 96--100%; these are observed software estimates, not validated measurements |
| Automatic interaction beeps | User reported none; finger event was logged, but automatic sound was not confirmed |

Baseline/command capture: 32 reading lines. Finger/target capture: 42 reading lines.
The firmware continued emitting readings through the command tests and captures.

## Flaws and limits

1. **Heart-rate estimates are unstable.** Estimates ranged from 42 to 187 bpm
   during the finger capture. The code uses the algorithm's validity flag and a
   broad numeric range; it has no additional signal-quality/stability gate. The
   cause of the variation was not isolated. Validity flags and a plausible SpO2
   number do not establish accurate measurements. No reference instrument was used.
2. **The temperature interaction rule misses this test target.** It requires the
   surface to exceed sensor ambient by 1.5 C for about 0.6 seconds. The greatest
   observed difference was only 0.84 C, even though the surface changed when the
   hand/target moved. Consequently there were zero warm-target events. A future
   revision should use a suitable baseline-change rule or explicitly requested
   measurement rather than promise detection of every hand movement.
3. **Automatic beep audibility is unresolved.** A finger event calls the same
   90 ms buzzer routine as commands, but the user reported no interaction beeps.
   One recording attempt reset into ROM and was discarded before the valid capture;
   its serial RTS setting was corrected and the board reset back into the sketch.
   Event logging does not prove an audible beep. Repeat an isolated placement test
   while listening; buzzer duration, driver and event timing need checking.
4. **Missing sensors are only initialized at startup.** The first uploaded run
   reported both missing; later, after another reset/upload, both responded. The
   reason for that change is not established. S diagnoses addresses but does not
   reinitialize an absent sensor; after correcting wiring/power, reset the board.
5. **Display has no touch input or readback.** Its visible operation was confirmed
   by the user. Touching the glass cannot trigger a beep with these connections.

## Changes made during testing

- Added a startup and S/SCAN I2C scan, including idle levels and address responses.
- Fixed stale-temperature presentation: after two seconds without valid readings,
  the display/log hides the temperature and resets the warm-target trigger state.
- Recompiled and uploaded the revised sketch. That freshness failure path was
  reviewed in code; no intentional live sensor disconnection was performed.

## Evidence in this workspace

- `../../.local/display-sensor-build.log`
- `../../.local/display-sensor-upload.log`
- `../../.local/display-sensor-hardware-test.log`
- `../../.local/display-sensor-finger-test.log`

The test serial port was closed after capture. The diagnostic remains flashed;
no Wi-Fi or backend connection is included. Supply/current safety and measurement
accuracy were not established by these software and interaction tests.
