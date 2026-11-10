# NeoGuard live-upload recovery

The `akena_firmware` sketch in this folder was recovered from the previously
compiled NeoGuard Wi-Fi build. The unrelated irrigation sketch currently at
`akena firmware/akena_firmware/akena_firmware.ino` was preserved unchanged.

The recovery handles a blocked upload queue: when the backend explicitly rejects
events, the complete request and response are saved to `/sync-rejected.ndjson`
on the SD card before the cursor advances. The original `/pending.ndjson` also
remains intact. Unknown responses, mismatched event IDs, failed archive writes,
and failed cursor writes retain the batch for retry. Rejected measurements are
not relabelled as accepted or given replacement timestamps.

Target: `esp32:esp32:esp32s3:CDCOnBoot=cdc`, Arduino ESP32 package 3.3.12.
Build output and logs: `.local/neoguard-live-build` and
`.local/neoguard-live-build.log` at the project root.

The temporary `.local/live-usb-relay.ps1` reads actual serial STATUS values and
the device RTC, uploads only available in-range parameters, and labels them
`poor` (unqualified estimates). It uses the website's existing API proxy. Stop
the relay before flashing; never run two serial readers concurrently.

Patient graphs require a clinical account. The presentation nurse account is
`nurse.demo`, scoped to clinic 2. Login details are in the private Downloads file
`NeoGuard_Presentation_Login.txt`; do not publish that file.
