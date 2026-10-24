# RGB and SD hardware test -- 24 October 2026

**Result: PASS for the functional checks performed.** The dedicated offline
diagnostic is uploaded to the attached ESP32-S3 on COM7. No fault was observed
in the tested RGB channels or SD file operations.

| Check | Result |
|---|---|
| Compile/link | Passed; 391730 bytes program, 24240 bytes static RAM |
| Upload | Passed; written flash hash verified |
| RGB red / green / blue | User confirmed each matches the screen label |
| RGB white / off | User confirmed both match |
| Manual commands / cycle | RED, GREEN, BLUE, WHITE, OFF and CYCLE executed; cycle left enabled |
| SD initialization | Mounted at 1 MHz using CS21/SCK40/MOSI41/MISO42 |
| Card report | SDHC/SDXC, 59638 MiB raw capacity; filesystem reports 59622 MiB |
| File creation and write | New temporary file, 512-byte deterministic pattern |
| Reopen/read/compare | All 512 bytes matched |
| Append and verification | Appended 128 bytes, reopened and compared all 640 bytes |
| Cleanup | Deleted own temporary file and checked its absence |
| Repeated operations | Four reported PASS attempts: startup plus three commanded retries |
| Joint load | Repeated SD test passed with RGB WHITE, another with RGB OFF, another with BLUE during cycle mode |

The startup capture contains a PASS status after attempt 1; detailed stage outputs
for that attempt were not all captured. Attempts 2--4 include complete stage/result
records. The final status reports SD_last_test=PASS and attempts=4, with no SD FAIL
record. RGB was confirmed by the user's observation, not inferred from output commands.

## Data handling and test limits

Formatting was explicitly disabled. Each attempt chose an unused `/ngrtestNNN.tmp`
path and touched only its own temporary file. In these successful runs it used
`/ngrtest000.tmp`, removed it, and could reuse that now-unused path. Existing user
files were not listed or opened for writing.

This establishes basic communication and small file operations with the LED and
status screen operating. It does not verify every card sector, advertised usable
capacity, endurance, power-loss recovery, long-term logging or maximum write speed.
The supply voltage/current and RGB resistor currents were not measured. SD status
on the screen is the most recent test result, not continuous card-presence detection.

The test sketch does not acquire temperature, oximetry or RTC readings. Those
previous source sketches remain in their folders. No Wi-Fi/backend connection is used.

## Evidence

- `../../.local/rgb-sd-build.log`
- `../../.local/rgb-sd-upload.log`
- `../../.local/rgb-sd-hardware-test.log`

The serial test connection was closed after recording. The RGB/SD diagnostic
remains flashed and cycles the LED. To stop the cycle, send OFF in Serial Monitor
at 115200 baud with newline enabled. SD repeats the card test.
