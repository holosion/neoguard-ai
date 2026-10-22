import json, math, heapq, time
from pathlib import Path
from collections import defaultdict
import pcbnew as p

ROOT = Path(__file__).resolve().parent
M = json.loads((ROOT / 'design_manifest.json').read_text())
LIB = Path(r'C:\Program Files\KiCad\10.0\share\kicad\footprints')
STEP = 0.254
X0, Y0, X1, Y1 = 20, 20, 160, 125
NX, NY = math.ceil((X1-X0)/STEP)+1, math.ceil((Y1-Y0)/STEP)+1
N = NX*NY
POWER = {'GND','V3V3','DEV3V3','EXT3V3','EXT5V','SD_VCC','BUZZ_VCC','BUZZ_SW'}
POS = {
 'J1':(35.052,48.006,0), 'J2':(55.118,34.036,90),
 'J3':(55.118,44.196,90), 'J4':(55.118,54.356,90),
 'J5':(80.01,28.956,0), 'J6':(149.098,96.012,0),
 'J7':(111.76,112.014,90), 'J8':(77.978,112.014,90),
 'J9':(35.052,112.014,90), 'JP1':(35.052,93.98,0),
 'JP2':(132.08,104.14,90), 'JP3':(77.978,93.98,0),
 'JP4':(130.048,54.102,0), 'R1':(54.102,39.116,0),
 'R2':(54.102,49.276,0), 'R3':(95.25,83.058,0),
 'R4':(95.25,91.186,0), 'R5':(95.25,99.314,0),
 'R6':(57.912,78.994,0), 'R7':(57.912,87.122,0),
 'Q1':(78.994,81.026,0), 'D1':(83.058,105.156,0),
 'C1':(54.102,64.008,0), 'C2':(64.008,64.008,0),
 'C3':(131.064,91.948,0), 'C4':(141.224,91.948,0), 'U2':(114.046,68.072,0), 'RV1':(140.208,69.088,0), 'R8':(133.096,81.026,0), 'C5':(126.492,67.056,0), 'C6':(104.14,69.088,0)
}
SHORT_VALUES = {
 'J1':'ESP32 CABLE', 'J2':'MAX30102', 'J3':'MLX90614', 'J4':'DS1302',
 'J5':'16x2 LCD ON BOARD', 'J6':'SD SPI', 'J7':'RGB CATHODE', 'J8':'BUZZER <=20mA',
 'J9':'REGULATED POWER', 'JP1':'3V3 SOURCE','JP2':'SD SUPPLY','JP3':'BUZZ SUPPLY',
 'JP4':'BL - DNP', 'Q1':'PN2222A', 'R1':'4k7 DNP','R2':'4k7 DNP'
}

def v(x,y): return p.VECTOR2I(round(x*1e6),round(y*1e6))
def xy(z): return (z.x/1e6,z.y/1e6)
def grid(x,y): return (round((x-X0)/STEP),round((y-Y0)/STEP))
def mm(i,j): return (X0+i*STEP,Y0+j*STEP)
def idx(i,j,z): return z*N+j*NX+i
def unpack(k):
 z,k=divmod(k,N); j,i=divmod(k,NX); return i,j,z

board=p.BOARD()
print('Creating board',flush=True)
board.SetCopperLayerCount(2)
nets={}
names=sorted({net for c in M['components'] for net in c['pins'].values() if net})
for i,name in enumerate(names,1):
 net=p.NETINFO_ITEM(board,'/'+name,i); board.Add(net); nets[name]=net
ncnet=p.NETINFO_ITEM(board,'unconnected-(J2-Pin_5-Pad5)',len(names)+1);board.Add(ncnet)
byref={}; pads=defaultdict(list)
mapping_file=ROOT/'schematic_ids.json'
ids=json.loads(mapping_file.read_text()) if mapping_file.exists() else {}
mapping=ids.get('paths',ids.get('full_paths',{})) or {ref:'/'+ids['root_uuid']+'/'+uid for ref,uid in ids.get('symbols',{}).items()}
for c in M['components']:
 print('Placing',c['ref'],flush=True)
 lib,name=c['footprint'].split(':')
 fp=p.FootprintLoad(str(LIB/(lib+'.pretty')),name)
 if not fp: raise ValueError(c['footprint'])
 fp.SetReference(c['ref']); fp.SetValue(c['value'])
 fp.SetFPID(p.LIB_ID(lib,name))
 fp.SetPosition(v(*POS[c['ref']][:2])); fp.SetOrientationDegrees(POS[c['ref']][2])
 fp.SetDNP(bool(c.get('dnp',False)))
 if c['ref'] in mapping:
  fp.SetPath(p.KIID_PATH(mapping[c['ref']]))
 board.Add(fp); byref[c['ref']]=fp
 fp.Value().SetVisible(False)
 fp.Reference().SetTextSize(v(.9,.9)); fp.Reference().SetTextThickness(int(.15e6))
 for pad in fp.Pads():
  net=c['pins'].get(pad.GetNumber())
  if net:
   pad.SetNet(nets[net]); pads[net].append(pad)
  elif c['ref']=='J2' and pad.GetNumber()=='5':pad.SetNet(ncnet)

# Four mounting holes, no plated copper ring.
holes=[]
for i,(x,y) in enumerate(((25,25),(156,24),(25,120),(155,120)),1):
 fp=p.FootprintLoad(str(LIB/'MountingHole.pretty'),'MountingHole_3.2mm_M3')
 fp.SetReference(f'H{i}'); fp.SetValue('M3 3.2mm NPTH'); fp.SetPosition(v(x,y))
 fp.SetAttributes(p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 fp.Value().SetVisible(False); fp.Reference().SetVisible(False); board.Add(fp); holes.append((x,y))

for a,b in [((X0,Y0),(X1,Y0)),((X1,Y0),(X1,Y1)),((X1,Y1),(X0,Y1)),((X0,Y1),(X0,Y0))]:
 sh=p.PCB_SHAPE(); sh.SetShape(p.SHAPE_T_SEGMENT); sh.SetLayer(p.Edge_Cuts)
 sh.SetStart(v(*a)); sh.SetEnd(v(*b)); sh.SetWidth(int(.05e6)); board.Add(sh)

def text(s,x,y,size=1.0,justify=p.GR_TEXT_H_ALIGN_CENTER):
 t=p.PCB_TEXT(board); t.SetText(s); t.SetPosition(v(x,y)); t.SetLayer(p.F_SilkS)
 size=max(.8,size)
 t.SetTextSize(v(size,size)); t.SetTextThickness(int(min(.16,size*.15)*1e6)); t.SetHorizJustify(justify)
 board.Add(t)

text('AKENA NEOGUARD  |  LCD CARRIER  |  REV C',90,25,1.5)
text('REVIEW PROTOTYPE - VERIFY LCD / MODULE DIMENSIONS',90,22.5,.9)
text('3V3 SENSORS  |  5V LCD VIA AHCT245  |  REGULATED INPUTS',90,121,1.0)
text('ONE SHUNT PER SELECTOR - DO NOT BRIDGE USB AND EXT POWER',90,117.5,.9)
text('USB powers ESP32 separately - see assembly guide',90,123,.75)


# Four dedicated LCD mounting holes. Their positions are an explicit WC1602A assumption.
for hole in byref['J5'].Pads():
 if not hole.GetNumber():
  hole.SetAttribute(p.PAD_ATTRIB_NPTH)
  hole.SetShape(p.PAD_SHAPE_CIRCLE);hole.SetSize(v(2.7,2.7));hole.SetDrillSize(v(2.7,2.7))
for fp in board.GetFootprints():
 fp.Reference().SetVisible(False)
for ref,label in {'J1':'ESP32-S3 CABLE','J2':'MAX30102','J3':'MLX90614','J4':'DS1302','J6':'SD CARD','J7':'RGB R G B GND','J8':'BUZZER + -','J9':'EXT 3V3 GND 5V','JP1':'3V3 SOURCE','JP2':'SD SUPPLY','JP3':'BUZZ SUPPLY','U2':'AHCT245 5V','RV1':'LCD CONTRAST','R8':'LCD LED 220R'}.items():
 x,y,r=POS[ref];text(ref+' '+label,x-2,y-4,0.85)
text('LCD1602: RS8 EN9 D4:10 D5:11 D6:12 D7:13',111,66,0.8)
text('LCD MOUNTING: WC1602A 80 x 36 mm ASSUMED',111,60,.8)
text('J1 IS A CABLE HEADER, NOT A DEVBOARD SOCKET',53,88,.8)
text('I2C SDA4 / SCL5',60,27,.85)
p.SaveBoard(str(ROOT/'NeoGuard.kicad_pcb'),board)
from route_lcd import run
run()
