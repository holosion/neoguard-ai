# SPI-D validation — 29 October 2026

KiCad 10.0.4 checks on the regenerated SPI revision:

- Schematic ERC: zero reported errors, warnings or exclusions.
- PCB DRC: zero reported violations, zero unconnected items, zero schematic-parity differences.
- Independent comparison: 26 carrier parts, 99 carrier pins, 18 firmware GPIO assignments and all 40 logical controller pins match the manifest/netlist/board.
- Intentional no-connects: 20 controller connections and 2 carrier connections (J1 pin22 and MAX30102 INT at J2 pin5).
- Two copper layers, 140 × 105 mm, filled ground pours and stitching vias.

Used pins connect through wires and named global nets. Matching global labels are electrical connections across the three sheets. Unused external controller connections have explicit KiCad no-connect X symbols.

The project retains its existing rule configuration. The JSON reports list ignored categories, including single global labels, SPICE model checks, footprint filters, missing courtyard and via centering; no new exclusions were added to obtain these results. U1 is a logical external interface with passive pin types, not a model of the development board's internal electronics. ERC cannot validate that internal circuitry.

The display is the firmware-confirmed ST7789 240×280 SPI module, previously called OLED. Screen supply is 3.3V; SPI signals use GPIO8–12. GPIO13 is unused. Backlight JP4 is normally open pending confirmation of the breakout's backlight input.

The exact purchased ESP32-S3 board, display/module header orders, mounting dimensions and current budget remain unconfirmed. J1 and J5 are functional cable headers, not fitted module sockets. The generated PCB has not been fabricated or powered. These checks do not prove hardware operation or medical suitability. No manufacturing files or order were released.
