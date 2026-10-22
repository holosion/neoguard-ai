# LCD-C verification record

22 October 2026. KiCad 10.0.4. This record applies only to the design in this folder.

## Checks completed

- Native schematic ERC: **0 reported violations**, including errors and warnings, on all three sheets.
- Native PCB DRC: **0 reported violations, 0 unconnected items, 0 schematic parity issues**, including errors and warnings.
- Independent manifest-to-schematic-to-PCB comparison: **134 electrical pins across 30 components**, no mismatch; **7 intentional no-connects** verified.
- Firmware comparison: **19 GPIO assignments**, no mismatch with the LCD integration sketch.
- Two copper layers; **140 x 105 mm** board outline. **63 non-ground routing connections** complete. Ground uses filled F.Cu/B.Cu zones with **80 stitching vias** and isolated-island removal.
- Signal width 0.30mm; power width 0.60mm; via diameter/drill 0.80/0.40mm; zone clearance 0.25mm. Default thermal gap/spoke 0.30/0.40mm. LCD RW pad5 uses a solid zone connection to avoid a starved thermal at this permanently grounded pin.
- LCD footprint has 16 numbered electrical pads, four nonplated 2.7mm mounting holes and a project-local STEP model. Four further 3.2mm mounting holes belong to the carrier board itself.
- Three PDF schematic pages rendered and visually reviewed. Final board preview generated with native KiCad 3D rendering; copper SVG exported from the board.
- The final design and its local LCD footprint are consistent with the schematic. Intentional NC net names match KiCad's schematic netlist.

## Scope of the reports

The raw ERC/DRC JSON files retain KiCad's own ignored-check metadata. Default ignored categories are not represented as checked; no new error exclusions were added to hide a failure. Native command-line runs emitted Windows registry preference warnings but successfully read the designs, generated reports, and produced the exports.

## Mechanical assumptions and unverified hardware

The assumed LCD is WC1602A-style, 80 x 36mm, with approximately 75 x 31mm mounting-hole centres and a 2.54mm-pitch, 16-pin header. The actual user's LCD has not been measured or positively identified. Spacer/socket height, screw clearance, module tolerances and enclosure fit are unverified.

J1 is a functional controller cable, not an ESP32 development-board socket. Sensor/SD/RTC/RGB/buzzer headers are functional harness interfaces, not verified purchased-module mounting patterns. Check module connector order, logic compatibility, supply ratings, current budget, reverse-power behaviour, RGB polarity and transistor pinout before fabrication or power-up.

No board has been ordered, fabricated, assembled, powered or medically validated. Clean design checks do not establish real sensor accuracy, patient safety or manufacturing approval. No fabrication Gerber release is included.
