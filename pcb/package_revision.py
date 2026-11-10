"""Publish consistent review files only after electrical and board checks pass."""
from pathlib import Path
import json,csv,hashlib,zipfile,shutil
root=Path(__file__).resolve().parent
erc=json.loads((root/'ERC.json').read_text())
drc=json.loads((root/'DRC.json').read_text())
verification=json.loads((root/'verification_summary.json').read_text())
assert erc['date'].startswith('2026-10-29') and drc['date'].startswith('2026-10-29')
assert not any(s['violations'] for s in erc['sheets'])
assert not any(drc[k] for k in ['violations','unconnected_items','schematic_parity'])
assert not verification['issues']
ids=json.loads((root/'schematic_ids.json').read_text())
with (root/'Controller-pins.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Logical pin (not physical position)','Connection'])
    w.writerows((n,net or 'NO CONNECT (X)') for n,net in ids['logical_controller']['pin_nets'].items())
(root/'VALIDATION.md').write_text('''# SPI-D validation — 29 October 2026

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
''')
(root/'START-HERE.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>NeoGuard SPI-D</title><style>body{font:17px system-ui;max-width:1100px;margin:40px auto;background:#f4f6f8;color:#172a36}h1{font-size:32px}img{width:100%;background:white;border:1px solid #ccc;margin:12px 0}a{color:#135f99}section{padding:24px;background:white;margin:20px 0}</style><h1>Akena NeoGuard · SPI display revision D</h1><p>29 October 2026 · ST7789 240×280 · ESP32-S3</p><section><p>Parallel LCD circuitry removed. Used connections match current firmware. Unused ESP32 external pins carry X marks.</p><p><a href="NeoGuard-schematic.pdf">Schematic PDF</a> · <a href="NeoGuard.kicad_pro">KiCad project</a> · <a href="Akena-SPI-PCB-project.zip">Portable project</a> · <a href="Connections.csv">Carrier wiring</a> · <a href="Controller-pins.csv">Controller pins</a> · <a href="VALIDATION.md">Validation</a></p><p>Checks: zero reported ERC/DRC violations, zero unrouted items and zero schematic-parity differences. Physical module fit remains unconfirmed; this is a cable-connected carrier.</p></section><h2>Carrier board</h2><img src="PCB-SPI.png" alt="SPI carrier board"><p><a href="PCB-layout.svg">Inspect copper and silkscreen</a></p><h2>System and unused controller pins</h2><img src="schematic-1.png" alt="System schematic"><h2>SPI display wiring</h2><img src="schematic-2.png" alt="SPI display schematic"><h2>Power and controller cable</h2><img src="schematic-3.png" alt="Power schematic"></html>''')
# Retire old entry points so the active folder cannot accidentally rebuild LCD-C.
backup=root/'.history'/'pre-spi-d-20261029'
for name in ['NeoGuard-lcd.kicad_sch','PCB-with-LCD.png','Akena-LCD-PCB-project.zip','prepare_lcd_design.py','route_lcd.py','schematic_pages.py.txt','build.log','update_spi_revision.py']:
    f=root/name
    if f.exists():
        if not (backup/name).exists():shutil.copy2(f,backup/name)
        assert (backup/name).is_file()
        f.unlink()
files=[f for f in root.iterdir() if f.is_file() and f.suffix not in ['.zip','.lck','.py','.prl'] and f.name!='release_checksums.json']
# Include the existing footprint libraries/models for portability, even when unused.
for dirname in ['Akena_LCD.pretty','models']:
    files.extend(f for f in (root/dirname).rglob('*') if f.is_file())
checksums={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
(root/'release_checksums.json').write_text(json.dumps(checksums,indent=2))
with zipfile.ZipFile(root/'Akena-SPI-PCB-project.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in files+[root/'release_checksums.json']:z.write(f,f.relative_to(root))
print('Packaged checked SPI-D design.')
