# Akena NeoGuard — SPI display revision D

Updated 29 October 2026. Open `NeoGuard.kicad_pro` in KiCad 10 or read `NeoGuard-schematic.pdf`.

The display is the ST7789 240×280 SPI screen, called OLED in earlier project notes and identified by the current firmware and hardware-test records. This design follows that interface.

## Changes

- Removed the 16×2 LCD, AHCT245 buffer, contrast trimmer and LCD backlight circuitry.
- Restored the eight-signal SPI display cable and optional backlight jumper.
- Exposed all 36 GPIO identities in the DevKitC-style external GPIO set plus 3V3, GND, EN and 5V. Every used pin connects through a wire and named net. Twenty unused external connections have no-connect X marks.
- GPIO13 and carrier J1 pin22 are unconnected. Leave J1 pin22 disconnected.
- Preserved the previous LCD project in `.history/pre-spi-d-20261029`.

## Display wiring

| J5 pin | Display signal | Connection |
|---|---|---|
| 1 | GND | Common ground |
| 2 | VCC | Selected V3V3 |
| 3 | SCK / SCL | GPIO12 |
| 4 | MOSI / SDA | GPIO11 |
| 5 | RST / RES | GPIO8 |
| 6 | DC | GPIO9 |
| 7 | CS | GPIO10 |
| 8 | BL / BLK | JP4 optional 3V3 backlight supply |

Screen SDA/SCL are SPI signals. Sensor I2C remains SDA=GPIO4, SCL=GPIO5. JP4 is normally open/DNP; fit only for a verified 3.3V-compatible backlight input with suitable current limiting. Firmware has no backlight GPIO.

RTC CLK/DAT/CE remain GPIO6/7/14. SD CS/SCK/MOSI/MISO remain GPIO21/40/41/42. Buzzer remains GPIO15 and RGB remains GPIO16/17/18.

## Controller and mechanical interface

U1 represents the offboard development board using logical GPIO identities, not physical pin positions. Duplicate supply/ground contacts are represented by common logical supply pins. X means no external carrier connection; EN, USB, strapping and memory circuitry retain their functions on the development board. GPIO26–34 are not external carrier interfaces. GPIO35–37 are unused and may be reserved by memory on some variants.

J1 is a 2×12 cable header, not a development-board socket. J5 is a 1×8 functional cable header, not a mechanically matched screen footprint. Assemble cables by signal name using Connections.csv. Exact controller model, module pin order and mounting dimensions still require confirmation.

## Power and assembly

All grounds join. No onboard regulator or reverse-polarity protection. J9 accepts regulated 3V3/GND/5V on pins1/2/3. External 5V is only needed if the SD or buzzer requires it; the display uses 3V3.

- JP1: one shunt; pins1–2 selects DEV3V3, pins2–3 selects EXT3V3. Never bridge both sources.
- JP2: pins1–2 selects 3V3 SD supply; pins2–3 selects 5V. Signals must remain 3.3V compatible.
- JP3: pins1–2 selects 3V3 buzzer supply; pins2–3 selects 5V.
- R1/R2: optional 4.7k I2C pull-ups to 3V3, normally DNP when fitted on modules.
- Q1: PN2222A E1/B2/C3; verify purchased pinout. R6=1k, R7=10k pulldown, D1 cathode to buzzer positive. Buzzer load assumption: at most 20mA.

Power controller and modules together. Verify regulator current capacity. Sensor breakouts must support 3.3V supply and I2C. RTC battery charging remains disabled in firmware.

## Files and regeneration

The root schematic uses NeoGuard-display.kicad_sch and NeoGuard-power.kicad_sch. Keep these with the local library and project. BOM.csv, Connections.csv, Controller-pins.csv, ERC.json, DRC.json and verification_summary.json describe this revision. Akena-SPI-PCB-project.zip is the portable review package.

Run build_schematic.py; export the KiCad XML netlist to NeoGuard.net.xml; run build_pcb.py and finish_board.py using KiCad Python; run verify_design.py, ERC and DRC with schematic parity. Export PDF and previews after changes. route_spi.py is the routing helper. The migration script is retained only in the history folder.

Checks establish connectivity and configured-rule compliance, not purchased-module fit, assembled operation or clinical suitability. See VALIDATION.md for results.

Controller reference: https://documentation.espressif.com/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
Firmware wiring: ../akena firmware/akena_firmware/README.md
