"""Independent manifest, schematic netlist, PCB and firmware pin comparison."""
import json, re, csv
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p

root=Path(__file__).resolve().parent
m=json.loads((root/'design_manifest.json').read_text())
board=p.LoadBoard(str(root/'NeoGuard.kicad_pcb'))
fps={fp.GetReference():fp for fp in board.GetFootprints()}
xml=ET.parse(root/'NeoGuard.net.xml').getroot()
schematic={}
for net in xml.findall('./nets/net'):
    for n in net.findall('node'):schematic[(n.attrib['ref'],n.attrib['pin'])]=net.attrib['name']
issues=[];pins=0;nc=0
for c in m['components']:
    fp=fps.get(c['ref'])
    if fp is None:issues.append('Missing footprint '+c['ref']);continue
    pads={pa.GetNumber():pa for pa in fp.Pads() if pa.GetNumber()}
    for pin,net in c['pins'].items():
        pins+=1;pad=pads.get(pin)
        if pad is None:issues.append('Missing pad '+c['ref']+'.'+pin);continue
        actual=pad.GetNetname().lstrip('/')
        sch=schematic.get((c['ref'],pin),'').lstrip('/')
        if net is None:
            nc+=1
            if actual and not actual.startswith('unconnected-'):issues.append(f'PCB NC connected {c["ref"]}.{pin}: {actual}')
            if sch and not sch.startswith('unconnected-'):issues.append(f'Schematic NC connected {c["ref"]}.{pin}: {sch}')
        else:
            if actual!=net:issues.append(f'PCB {c["ref"]}.{pin}: {actual} != {net}')
            if sch!=net:issues.append(f'Schematic {c["ref"]}.{pin}: {sch} != {net}')

expected={'SDA_PIN':4,'SCL_PIN':5,'RTC_CLK':6,'RTC_DAT':7,'RTC_RST':14,'LCD_RS':8,'LCD_EN':9,'LCD_D4':10,'LCD_D5':11,'LCD_D6':12,'LCD_D7':13,'SD_CS':21,'SD_SCK':40,'SD_MOSI':41,'SD_MISO':42,'BUZZER':15,'RED_LED':16,'GREEN_LED':17,'BLUE_LED':18}
firmware=(root.parent/'akena firmware/akena_firmware/akena_firmware.ino').read_text()
for name,number in expected.items():
    if not re.search(r'\b'+name+r'\s*=\s*'+str(number)+r'\b',firmware):issues.append('Firmware pin mismatch '+name)
    net=next((n for c in m['components'] for n in c['pins'].values() if n and n.endswith('GPIO'+str(number))),None)
    if net is None:issues.append('No net for GPIO'+str(number))
    elif schematic.get(('U1',str(number)))!=net:issues.append('Logical controller mismatch GPIO'+str(number))

lcd=fps['J5']
lcdholes=[pa for pa in lcd.Pads() if not pa.GetNumber() and pa.GetAttribute()==p.PAD_ATTRIB_NPTH]
if len(lcdholes)!=4:issues.append('LCD needs four mounting holes')
if len(list(lcd.Models()))<1:issues.append('LCD 3D model missing')
out={'revision':'LCD-C','KiCad':p.Version(),'components':len(m['components']),'electrical_pins_checked':pins,'intentional_no_connects':nc,'firmware_gpio_assignments_checked':len(expected),'board_dimensions_mm':[140,105],'copper_layers':board.GetCopperLayerCount(),'lcd':{'footprint':str(lcd.GetFPID().GetLibItemName()),'module_dimensions_assumed_mm':[80,36],'hole_centres_assumed_mm':[75,31],'npth_holes':len(lcdholes),'drill_mm':2.7,'actual_module_fit_confirmed':False},'issues':issues}
(root/'verification_summary.json').write_text(json.dumps(out,indent=2))
with (root/'BOM.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Reference','Value','Footprint','Fit'])
    for c in m['components']:w.writerow([c['ref'],c['value'],c['footprint'],'DNP' if c.get('dnp') else 'FIT'])
with (root/'Connections.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Reference','Pin','Net'])
    for c in m['components']:
        for pin,net in c['pins'].items():w.writerow([c['ref'],pin,net or 'NO CONNECT'])
print(json.dumps(out,indent=2))
if issues:raise SystemExit(1)
