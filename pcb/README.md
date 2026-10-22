# Akena NeoGuard LCD PCB — start here

Created 22 October 2026. Open **START-HERE.html** for the picture overview.

This is a **140 × 105 mm, two-layer carrier PCB** matching the GPIO map in `akena firmware/akena_firmware/akena_firmware.ino`. The **16×2 LCD is physically mounted on the carrier**, with its complete footprint, four mounting holes, 16-pin interface, contrast adjustment, backlight resistor and 3D model. The previous ST7789 design in `../schematic` is preserved separately.

## Files to open

- **PCB-with-LCD.png** — rendered view with the LCD fitted. The unpowered LCD surface is blank in the stock 3D model.
- **PCB-layout.svg** — actual copper routing, silkscreen and board outline; zoom to inspect.
- **NeoGuard-schematic.pdf** — three-sheet schematic: system connections, LCD/buffer, power/controller cable.
- **NeoGuard.kicad_pro** — editable KiCad 10 project. Open its schematic or PCB editor to modify the design.
- **NeoGuard.kicad_pcb** — native PCB layout.
- **NeoGuard.kicad_sch** — root schematic; keep the two child sheets and local symbol/footprint libraries together.
- **Akena-LCD-PCB-project.zip** — portable editable project and review files.
- **BOM.csv**, **Connections.csv** — components and exact numbered electrical connections.
- **VALIDATION.md**, **ERC.json**, **DRC.json**, **verification_summary.json** — checks and limitations.

## Physical fit: confirmation still needed

The user has not supplied the actual LCD and development-board model numbers or measurements. This is a checked electrical carrier design, **not a confirmed physical fit for unmeasured modules**.

- LCD assumption: **WC1602A-compatible 80 × 36 mm**, 16 pins at **2.54 mm pitch**, mounting-hole centres approximately **75 × 31 mm**. Four **2.7 mm nonplated holes** are provided. Confirm the LCD's actual hole diameters and header position before making the board.
- Mount the LCD with a suitable 1×16 socket/header and four insulating spacers matching its actual underside clearance. Socket and spacer height must be measured; a rendered model does not establish this fit.
- ESP32-S3 remains connected through **J1, a functional 2×12 cable header**. It is **not a development-board socket**. J1 pin numbers are cable pin numbers, not ESP32 header positions. The firmware GPIO numbers are shown in the schematic and connection CSV. J1 pin22 now carries GPIO13 / LCD D7.
- Sensor, SD, RGB, RTC and buzzer modules connect through labelled functional headers. Their headers are not claimed to reproduce purchased breakout pin order, module outlines or mounting holes. Wire cables by signal name.

## Preserved GPIO assignments

| Function | ESP32-S3 GPIO |
| --- | --- |
| MAX30102 + MLX90614 SDA | 4 |
| MAX30102 + MLX90614 SCL | 5 |
| DS1302 CLK / DAT / CE | 6 / 7 / 14 |
| LCD RS / EN | 8 / 9 |
| LCD D4 / D5 / D6 / D7 | 10 / 11 / 12 / 13 |
| SD CS / SCK / MOSI / MISO | 21 / 40 / 41 / 42 |
| Buzzer control | 15 |
| RGB red / green / blue | 16 / 17 / 18 |

## LCD electrical interface

U2 must be **SN74AHCT245N in DIP-20**, powered from regulated 5V. **Do not substitute a 74HC245**: AHCT input thresholds are suitable for the ESP32's 3.3V outputs. DIR is tied high and OE low for A-to-B operation. Six channels carry RS, EN and D4–D7. Unused A6/A7 inputs are grounded and unused B6/B7 outputs are left open. The schematic uses a custom fixed-direction symbol with the device's actual pin numbers.

LCD pin5 RW is permanently grounded, so the controller never reads a 5V LCD bus. RV1 is a 10k contrast trimmer. R8 is an external 220-ohm backlight resistor; verify acceptable brightness and current against the purchased module. C5 provides local 100nF buffer bypass and C6 provides LCD-rail bulk storage.

The carrier also includes the previously recommended transistor buzzer driver, 1k base resistor, 10k base pulldown and correctly oriented flyback diode. It uses the same GPIO15, but it **does not reproduce direct GPIO-to-buzzer wiring**. Q1 is PN2222A with E1/B2/C3; verify the purchased transistor's pinout. The intended buzzer load is no more than 20mA.

## Power and assembly

All grounds join. **J9 requires regulated inputs; there is no onboard regulator or power protection.** J9 pin1 = external 3V3, pin2 = GND, pin3 = external 5V. External 5V is required for the LCD and U2. ESP32 USB remains on the external development board.

- JP1: fit **one shunt only**. Pins1–2 select ESP32 DEV3V3; pins2–3 select external EXT3V3. Do not bridge both sources.
- JP2: pins1–2 select 3V3 for the SD breakout; pins2–3 select 5V. Choose using the actual breakout specifications. SD signal levels must remain ESP32-compatible.
- JP3: pins1–2 select 3V3 for the buzzer; pins2–3 select 5V. Match its rating.
- This revision assumes MAX30102 and MLX90614 breakouts compatible with a **3.3V supply and 3.3V I2C**. A 5V-only temperature sensor variant requires redesign or an appropriate external interface.
- R1/R2 are optional 4.7k I2C pull-ups and normally DNP when breakout pull-ups are already present. Never pull SDA/SCL up to 5V.
- Power the ESP32 and carrier together; no isolation for independently powered signal lines is provided. Verify regulator capacity and the assembled current budget before power-up.
- Confirm common-cathode RGB wiring and use one resistor per colour. CR2032 RTC charging remains disabled in firmware.

## Checks and remaining work

Native KiCad ERC and DRC include errors and warnings and report zero violations. DRC also reports zero unrouted items and zero schematic parity issues. Independent checks compare 134 component pins, seven intentional no-connects and all 19 firmware GPIO assignments with no mismatch.

These checks establish file connectivity and rule compliance, not purchased-part fit, assembled electrical operation, manufacturer-specific DFM or medical suitability. **Confirm actual module dimensions, pin orders, voltages and supplies before fabrication.** No board has been fabricated or powered, and no manufacturing order was placed. Gerber release files are not included in this review package.

## Local regeneration

The generators are retained for reproducibility in this workspace. `prepare_lcd_design.py` uses the earlier `../schematic` generators as a starting point and does not edit that folder. Run prepare, build the schematic, export its KiCad XML netlist, build the PCB with KiCad Python, run `finish_board.py`, rebuild the schematic/netlist to include the project-local LCD footprint, and run ERC/DRC plus `verify_design.py`. Re-export previews after changes. The ZIP contains the editable native design and assets, not the workspace-dependent generator pipeline.

The local LCD footprint adapts KiCad's standard WC1602A footprint: its four mounting pads are nonplated 2.7mm holes. The LCD's grounded RW pad uses a solid zone connection; other ground pads use thermal connections. Standard KiCad models are used for the preview, and the LCD STEP model is included locally.

References: [TI SN74AHCT245 datasheet](https://www.ti.com/lit/gpn/SN74AHCT245), [KiCad footprint libraries](https://gitlab.com/kicad/libraries/kicad-footprints), [Wincom WC1602A dimensions](https://nettigo.eu/attachments/53). These references describe assumed parts, not an identification of the user's hardware.
