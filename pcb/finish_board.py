"""Finish the local LCD footprint, NC identities, model paths and readable silk."""
from pathlib import Path
import json, shutil, math
import xml.etree.ElementTree as ET
import pcbnew as p

root=Path(__file__).resolve().parent
board=p.LoadBoard(str(root/'NeoGuard.kicad_pcb'))
def v(x,y):return p.VECTOR2I(round(x*1e6),round(y*1e6))
def box(item):
    b=item.GetBoundingBox();return b.GetX()/1e6,b.GetY()/1e6,(b.GetX()+b.GetWidth())/1e6,(b.GetY()+b.GetHeight())/1e6
def intersects(a,b,gap=.3):return a[0]<b[2]+gap and a[2]>b[0]-gap and a[1]<b[3]+gap and a[3]>b[1]-gap
fps={f.GetReference():f for f in board.GetFootprints()}

# Name intentional NC nets exactly as KiCad's schematic netlist does.
xml=ET.parse(root/'NeoGuard.net.xml').getroot()
for net in xml.findall('./nets/net'):
    name=net.attrib['name']
    if not name.startswith('unconnected-'):continue
    for node in net.findall('node'):
        f=fps.get(node.attrib['ref'])
        if f:
            pad=next(pa for pa in f.Pads() if pa.GetNumber()==node.attrib['pin'])
            n=board.FindNet(name)
            if not n or n.GetNetCode()<0:
                n=p.NETINFO_ITEM(board,name);board.Add(n)
            pad.SetNet(n)

# Keep the modified mounting-hole footprint and the LCD model in the project.
modeldir=root/'models';modeldir.mkdir(exist_ok=True)
shutil.copy2(Path(r'C:\Program Files\KiCad\10.0\share\kicad\3dmodels\Display.3dshapes\WC1602A.step'),modeldir/'WC1602A.step')
lcd=fps['J5']
# RW is permanently grounded. Use a solid copper connection on this one pad
# because nearby LCD signals leave only one usable top-layer thermal spoke.
next(pa for pa in lcd.Pads() if pa.GetNumber()=='5').SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
for model in lcd.Models():model.m_Filename='${KIPRJMOD}/models/WC1602A.step'
lcd.SetFPID(p.LIB_ID('Akena_LCD','LCD1602_80x36_Mounting'))
lib=root/'Akena_LCD.pretty';lib.mkdir(exist_ok=True)
p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(lib),lcd)
m=json.loads((root/'design_manifest.json').read_text())
next(c for c in m['components'] if c['ref']=='J5')['footprint']='Akena_LCD:LCD1602_80x36_Mounting'
(root/'design_manifest.json').write_text(json.dumps(m,indent=2))
libs=['Capacitor_THT','Connector_PinHeader_2.54mm','Diode_THT','Package_TO_SOT_THT','Resistor_THT','Display','Package_DIP','Potentiometer_THT','MountingHole']
entries=''.join(f'(lib (name "{n}") (type "KiCad") (uri "${{KICAD10_FOOTPRINT_DIR}}/{n}.pretty") (options "") (descr "KiCad stock"))' for n in libs)
entries+='(lib (name "Akena_LCD") (type "KiCad") (uri "${KIPRJMOD}/Akena_LCD.pretty") (options "") (descr "LCD with four nonplated mounting holes"))'
(root/'fp-lib-table').write_text('(fp_lib_table (version 7) '+entries+')\n')

# Reference/value field text is on Fab or hidden; silk captions avoid body envelopes,
# solder-mask openings, vias and other captions instead of hiding DRC errors.
for d in list(board.GetDrawings()):
    if isinstance(d,p.PCB_TEXT):board.Delete(d)
obstacles=[]
for fp in board.GetFootprints():
    fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
    shapes=[box(d) for d in fp.GraphicalItems() if d.GetLayer()==p.F_CrtYd]
    if shapes:
        obstacles.append((min(b[0] for b in shapes),min(b[1] for b in shapes),max(b[2] for b in shapes),max(b[3] for b in shapes)))
    for pad in fp.Pads():obstacles.append(box(pad))
for t in board.GetTracks():
    if isinstance(t,p.PCB_VIA):obstacles.append(box(t))

placed=[]
def caption(text,x,y,size=.85):
    t=p.PCB_TEXT(board);t.SetText(text);t.SetLayer(p.F_SilkS);t.SetTextSize(v(size,size));t.SetTextThickness(round(.13e6))
    candidates=[(x,y)]
    offsets=[(dx,dy) for dx in range(-24,25) for dy in range(-20,21)]
    offsets.sort(key=lambda q:q[0]*q[0]+q[1]*q[1])
    candidates.extend((x+dx*.5,y+dy*.5) for dx,dy in offsets)
    candidates.extend(sorted(((xx,yy) for xx in range(25,156,2) for yy in range(23,123,2)),key=lambda q:math.dist(q,(x,y))))
    for xx,yy in candidates:
        t.SetPosition(v(xx,yy));b=box(t)
        if b[0]<21 or b[1]<21 or b[2]>159 or b[3]>124:continue
        if any(intersects(b,o) for o in obstacles+placed):continue
        board.Add(t);placed.append(b);return
    raise RuntimeError('No clear silkscreen position: '+text)

caption('AKENA NEOGUARD | LCD CARRIER C',90,23.5,1.25)
caption('VERIFY MODULE DIMENSIONS BEFORE MANUFACTURE',90,120,.85)
caption('3V3 SENSORS | 5V LCD | REGULATED INPUTS',90,123,.8)
labels={'J1':'ESP32-S3 CABLE','J2':'MAX30102','J3':'MLX90614','J4':'DS1302 RTC','J6':'SD CARD','J7':'RGB R G B GND','J8':'BUZZER + -','J9':'EXT 3V3 GND 5V','JP1':'3V3 SOURCE','JP2':'SD SUPPLY','JP3':'BUZZ SUPPLY','U2':'AHCT245 5V','RV1':'CONTRAST','R8':'LCD LED 220R'}
for ref,label in labels.items():
    fp=fps[ref];pos=fp.GetPosition();caption(ref+' '+label,pos.x/1e6,pos.y/1e6-4)
board.BuildConnectivity()
if not p.ZONE_FILLER(board).Fill(board.Zones()):raise RuntimeError('Zone refill failed')
p.SaveBoard(str(root/'NeoGuard.kicad_pcb'),board)
summary=json.loads((root/'routing_summary.json').read_text());summary['revision']='LCD-C';(root/'routing_summary.json').write_text(json.dumps(summary,indent=2))
print('Saved local LCD footprint/model, exact NC nets and collision-aware silkscreen.')
