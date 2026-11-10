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
    for graphic in fp.GraphicalItems():
        if graphic.GetLayer()==p.F_SilkS:obstacles.append(box(graphic))
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

caption('AKENA NEOGUARD | SPI DISPLAY REV D',90,23.5,1.25)
caption('VERIFY MODULE DIMENSIONS BEFORE MANUFACTURE',90,120,.85)
caption('3V3 SENSORS | 3V3 DISPLAY | REGULATED INPUTS',90,123,.8)
labels={'J1':'ESP32-S3 CABLE','J2':'MAX30102','J3':'MLX90614','J4':'DS1302 RTC','J6':'SD CARD','J7':'RGB R G B GND','J8':'BUZZER + -','J9':'EXT 3V3 GND 5V','JP1':'3V3 SOURCE','JP2':'SD SUPPLY','JP3':'BUZZ SUPPLY','J5':'ST7789 SPI','JP4':'BL - DNP'}
for ref,label in labels.items():
    fp=fps[ref];pos=fp.GetPosition();caption(ref+' '+label,pos.x/1e6,pos.y/1e6-4)
for ref in ['R1','R2','R3','R4','R5','R6','R7','C1','C2','C3','C4','Q1','D1']:
    fp=fps[ref];pos=fp.GetPosition();caption(ref,pos.x/1e6,pos.y/1e6-3,.85)
board.BuildConnectivity()
if not p.ZONE_FILLER(board).Fill(board.Zones()):raise RuntimeError('Zone refill failed')
p.SaveBoard(str(root/'NeoGuard.kicad_pcb'),board)
summary=json.loads((root/'routing_summary.json').read_text());summary['revision']='SPI-D';(root/'routing_summary.json').write_text(json.dumps(summary,indent=2))
print('Saved exact NC nets and readable SPI carrier silkscreen.')
