# NeoGuard carrier schematic and PCB — revision B

This KiCad project connects the existing ESP32-S3 development board to offboard MAX30102, MLX90614, DS1302, ST7789 and microSD modules, plus an external RGB LED and a small active buzzer. The GPIO assignments follow the current `akena firmware/akena_firmware/akena_firmware.ino` source.

Revision B redraws the main schematic around an explicit **U1 ESP32-S3 development-board symbol**, with visible signal wires to every peripheral. A separate sheet contains the carrier harness and power-selection detail. U1 is a functional GPIO view of the existing offboard board: its pin identifiers are GPIO/function names, **not its unknown physical header positions**. U1 has no PCB footprint and is excluded from the carrier board and component BOM; the existing ESP32 board remains required offboard hardware. Native KiCad ERC, PCB DRC and schematic parity checks pass, with zero reported violations or unrouted items. See `VALIDATION.md` for the actual checks and their limits.

The controller connects through a **labelled 2x12 cable header, J1**. J1 is **not a socket for an ESP32-S3 development board**. “Standard ESP32-S3 dev module” does not establish the physical header arrangement. Make a wire harness from J1 to the GPIO labels on the actual board. All other module connectors are also functional harness connectors: their pin order must be mapped to the printed labels on each module, rather than assumed to match its physical header.

This is an unassembled prototype design, **not fabrication-approved or a clinically validated monitor**. Module power variants, actual headers, backlight requirements, current consumption and the assembled circuit remain to be checked. Schematic/PCB checks do not establish physical sensor accuracy or resolve a firmware fault.

## Project files

The native files were created with **KiCad 10.0.4**. Open them with **KiCad 10 or newer**; earlier releases may not read this file format.

- `NeoGuard.kicad_pro` — open this in KiCad.
- `NeoGuard.kicad_sch` — editable main electrical schematic with the ESP32-S3 and visible peripheral signal connections; keep its associated power/harness child sheet with the project.
- `NeoGuard-power.kicad_sch` — second schematic sheet, containing the real cable header and power-selection circuits.
- `NeoGuard.kicad_pcb` — editable two-layer carrier layout.
- `output/pdf/NeoGuard-schematic.pdf` — exported two-page schematic for viewing/printing.
- `BOM.csv` — board parts and offboard hardware requirements.
- `Wiring.csv` — carrier connector and selector pin numbers.
- `ESP32-connections.csv` — the 20 logical ESP32 GPIO/power connections, separately identified from physical header positions.
- `pcb-3d-preview.png` — native KiCad 3D rendering of the carrier.
- `ground-plane-preview.png` — bottom copper view, including the filled GND region.
- `design_manifest.json` — shared carrier component/net definition; U1 is an additional offboard documentation symbol.

The schematic and PCB are the design artifacts. Any exported manufacturing files remain prototype outputs until the verification steps below are completed. Open and review the actual current files in KiCad before ordering a board.

If KiCad was already open while these files changed, reload the project/sheets and PCB from disk to see revision B. Save any separate unsaved edits you want to retain before reloading.

The current carrier outline is **140 x 105 mm**, with a two-copper-layer, 1.6 mm board definition and four 3.2 mm unplated M3 mounting holes. Verify the actual enclosure, standoffs, screw clearances and component heights. The sensors, display, RTC, SD module and ESP32 board are offboard cable-connected parts, so their mechanical mounting is not designed here.

## Revision B copper and layout

The carrier remains a two-layer board. It now has a filled **B.Cu GND region** and a matching **F.Cu GND pour**, linked by **75 GND vias** distributed around the edge, inside the board and near module returns. Native fill removes isolated islands. Grounded through-hole pads use thermal reliefs with a 0.30 mm gap and 0.40 mm spokes; zone clearance is 0.25 mm. The bottom layer still carries a small number of signal/power crossings, so this is not a completely unbroken dedicated ground layer.

Routing uses 45-degree runs and grouped signal channels, with 0.30 mm signal tracks, 0.60 mm power tracks and 0.80/0.40 mm vias. The outline has small chamfered corners and the board is labelled NeoGuard revision B. These layout improvements do not establish physical hardware performance.

When mounting the offboard ESP32-S3 board, keep its antenna clear of the carrier's copper ground area and nearby metal, following that exact board/module manufacturer's antenna keepout requirements. For a PCB-antenna module, Espressif recommends placing the antenna outside the base-board edge where possible; see its [ESP32-S3 layout guidance](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html). No fictitious ESP32 antenna footprint/keepout is assigned on this cabled carrier. RF performance has not been validated.

## Power and jumpers

**There is no voltage regulator, battery charger, reverse-polarity protection or galvanic isolation on this carrier.** J9 accepts already regulated supplies. Connect every ground together. Never apply 5 V to a 3.3 V signal or rail.

| Selector | Pins 1–2 | Pins 2–3 | Required action |
|---|---|---|---|
| JP1: carrier 3.3 V source | ESP32 board DEV3V3 → V3V3 | External regulated EXT3V3 → V3V3 | Choose one source only. Confirm the ESP32 regulator can supply all carrier/module loads before using DEV3V3. |
| JP2: SD module supply | V3V3 → SD_VCC | EXT5V → SD_VCC | Select only after identifying the SD breakout’s rated VIN and 3.3 V logic compatibility. A bare SD card never receives 5 V. |
| JP3: buzzer supply | V3V3 → BUZZ_VCC | EXT5V → BUZZ_VCC | Match the buzzer’s rated voltage. Design target: low-current active buzzer, 20 mA maximum. |
| JP4: TFT backlight | Connects V3V3 to TFT_BL | Not applicable | **Leave open by default.** Fit only after confirming BL/BLK is a 3.3 V-compatible input with the required current limiting/driver already present. |

JP1, JP2 and JP3 each take **one shunt only**. Fitting two shunts shorts supply rails; at JP2/JP3 this can put 5 V onto the 3.3 V rail. Set jumpers only with all power disconnected. An unset voltage selector leaves its load unpowered.

J9 pin 1 is **external regulated 3.3 V**, pin 2 is GND and pin 3 is **external regulated 5 V**. The 5 V input is optional and feeds only loads deliberately selected through JP2/JP3. Do not connect external supply positives directly to ESP32 USB/5V/3V3 outputs. JP1 separates the selected positive rails but does not isolate GPIOs: power the controller and peripherals together to avoid signal/pull-up back-powering an unpowered board.

The U1 development-board **3V3** function connects to **DEV3V3**, then JP1 selects whether DEV3V3 or EXT3V3 feeds the carrier **V3V3** rail. There is no direct DEV3V3-to-V3V3 bypass. Keep this distinction when making the harness or editing the drawing.

MAX30102, MLX90614, DS1302 and ST7789 connectors use the selected V3V3 rail in this revision. Use **3.3 V-compatible breakout modules**. A 5 V MLX90614 variant or differently powered display needs a revised power/level-translation circuit before connection. Existing breakout regulators/level shifters must be checked; their presence cannot be assumed. Check supply voltage at each connector under Wi-Fi, display, SD-write and buzzer load.

## Connections and firmware settings

| Peripheral | ESP32 GPIO mapping | Implementation |
|---|---|---|
| MAX30102 | SDA4, SCL5 | I2C address 0x57; INT is deliberately unconnected. |
| MLX90614 | SDA4, SCL5 | I2C address 0x5A; object/surface and ambient temperature. |
| DS1302 | CLK6, DAT7, CE/RST14 | Three-wire RTC; not an I2C DS3231. Use its existing CR2032 module and disable trickle charging. |
| ST7789 display | RST8, DC9, CS10, MOSI11, SCK12 | Default display: 240x280 SPI TFT, mode 0, rotation 0; current firmware uses 1 MHz. |
| microSD | CS21, SCK40, MOSI41, MISO42 | Independent SPI bus, not shared with the TFT. |
| Buzzer control | GPIO15 | Active-high transistor driver. |
| RGB LED | Red16, green17, blue18 | External common-cathode LED; each anode has an onboard 330-ohm series resistor. |

Use `Wiring.csv` for exact carrier connector numbers and `ESP32-connections.csv` for logical GPIO/function identifiers. GPIO labels are not physical ESP32 header positions. GPIO40/41/42 must be exposed and available on the actual ESP32-S3 board; do not simultaneously use their external JTAG functions. Do not leave an older parallel LCD attached: its GPIO8–13 assignments overlap this TFT wiring.

R1/R2 are optional **4.7 kohm I2C pull-ups** to V3V3, **DNP by default**. Many sensor breakouts already contain pull-ups. Inspect the modules and measure effective pull-up resistance before fitting additional ones. Pull-ups must not connect the bus to 5 V. Keep the harness short; the design follows the current 100 kHz I2C configuration.

The user calls the screen an “OLED”, but the recorded working isolated display test uses **ST7789 TFT**. This carrier implements that default. An SSD1306/SH1106 OLED is not a drop-in substitute for J5; a genuinely different display needs a correctly wired adaptor and its own verified firmware configuration. No OLED adaptor or alternative board layout is implemented here.

## RGB, buzzer and component orientation

J7 pins 1/2/3 go to the external LED’s red/green/blue anodes; pin 4 goes to its common cathode. Identify these leads on the actual LED. This is not an addressable onboard RGB LED. The current firmware configuration is `RGB_COMMON_ANODE=false`.

J8 pin 1 goes to active buzzer positive; pin 2 goes to switched negative. R6 is 1 kohm from GPIO15 to Q1 base, and R7 is a 10 kohm base-to-ground pull-down. Q1 is the specified **PN2222A, pad 1 = emitter, pad 2 = base, pad 3 = collector**. Verify the purchased manufacturer/package against its datasheet before assembly. A part merely marked “2N2222” or a P2N2222A may have a different pinout and must not be assumed interchangeable. The TO-92 wide footprint may require careful lead forming.

D1 is a 1N5819 flyback diode: **band/cathode pad 1 → BUZZ_VCC**, anode pad 2 → BUZZ_SW/Q1 collector. This protects the switch with an inductive buzzer. Verify the actual buzzer is within the 20 mA design target and Q1 saturates under load; do not infer permitted switching current from a transistor’s absolute-maximum rating alone. A higher-current load needs a revised driver. A three-pin buzzer module with its own driver is an unimplemented alternative, not a direct J8 substitute.

C1/C3 are 100 nF non-polarized bypass capacitors. C2/C4 are 100 uF, at least 10 V polarized capacitors: **pad 1 is positive**, pad 2 is ground. Match component dimensions/lead pitch to the actual footprints before buying or fitting parts.

## Assembly and first checks

1. Check the exact ESP32 board and every module’s printed pin labels, rated supply and logic levels. Confirm the selected headers/parts physically fit their footprints and enclosure. Treat `Wiring.csv` as the carrier-side pinout; make labelled crossover harnesses where needed.
2. With power disconnected and modules unplugged, inspect soldering. Check that V3V3, EXT5V and GND are not shorted. Verify Q1, diode and electrolytic orientation. Leave R1/R2 unpopulated and JP4 open initially.
3. Select exactly one JP1 source. Set JP2/JP3 only after identifying the attached SD module and buzzer. Bring up the unconnected carrier with a current-limited supply and verify voltages at J2–J6/J8. Stop if current or voltage is unexpected.
4. Disconnect power, connect the controller harness and one verified module at a time, then test. Verify the J1 pin-1 mark and ground continuity before powering again. Power controller and peripherals together.
5. Test the ST7789 with the existing `akena firmware/display_check/display_check.ino` configuration. Connect JP4 only if the backlight circuit is verified. The existing blank integrated-screen problem is still a firmware/hardware integration investigation; this carrier does not guarantee a fix.
6. Test I2C detection (0x57/0x5A), RTC read/write, SD file writes, each LED channel and buzzer. Use native USB serial at 115200 with ESP32-S3 USB CDC On Boot enabled. Keep CR2032 charging disabled.
7. Run full firmware with SD, display and Wi-Fi simultaneously and measure loaded rails. Confirm real readings, local alarms, backend acknowledgement and offline replay using the existing device/session setup. Record physical results before treating the prototype as verified.

## Design references and limits

- Firmware pin source: `../akena firmware/akena_firmware/akena_firmware.ino`, especially the constants near the beginning. Current display and power assumptions also appear in its README.
- Earlier circuit guide: `../firmware/neoguard_system/README.md`; resistor/transistor recommendations were carried forward while the latest GPIO map takes precedence.
- [KiCad schematic documentation](https://docs.kicad.org/10.0/en/eeschema/eeschema.html) and [PCB documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html) describe project editing, ERC and DRC. Checks do not replace real part/pin verification.
- [onsemi PN2222A datasheet](https://www.onsemi.com/pdf/datasheet/pn2222a-d.pdf) identifies the intended E/B/C device. [P2N2222A datasheet](https://www.onsemi.com/pdf/datasheet/p2n2222a-d.pdf) is provided only to illustrate a different pin order; that part is not the selected Q1.
- [Espressif ESP32-S3 datasheet](https://documentation.espressif.com/esp32_s3_datasheet_en.pdf) is the silicon reference; the actual development-board header layout still needs its own confirmation.

Clinical thresholds and networking are implemented in firmware/backend, not in this passive carrier. This project adds no medical isolation, patient protection circuitry, certified alarm function or clinical validation.
