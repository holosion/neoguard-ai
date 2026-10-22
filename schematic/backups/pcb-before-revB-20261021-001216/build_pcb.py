"""Build the NeoGuard module carrier using installed KiCad pcbnew.

The manifest is authoritative. Routing is deterministic two-layer Manhattan A*;
actual KiCad DRC remains the final geometrical/connectivity check.
"""
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
 'J1':(35.052,48.006,0), 'J2':(64.008,34.036,90),
 'J3':(83.058,34.036,90), 'J4':(107.95,34.036,90),
 'J5':(149.098,45.974,0), 'J6':(149.098,84.074,0),
 'J7':(111.76,112.014,90), 'J8':(77.978,112.014,90),
 'J9':(35.052,112.014,90), 'JP1':(35.052,93.98,0),
 'JP2':(132.08,91.948,0), 'JP3':(77.978,93.98,0),
 'JP4':(130.048,54.102,0), 'R1':(58.928,49.022,0),
 'R2':(58.928,57.15,0), 'R3':(95.25,83.058,0),
 'R4':(95.25,91.186,0), 'R5':(95.25,99.314,0),
 'R6':(57.912,78.994,0), 'R7':(57.912,87.122,0),
 'Q1':(78.994,81.026,0), 'D1':(83.058,105.156,0),
 'C1':(67.056,40.132,0), 'C2':(55.118,40.132,0),
 'C3':(125.984,77.978,0), 'C4':(140.208,77.978,0)
}
SHORT_VALUES = {
 'J1':'ESP32 CABLE', 'J2':'MAX30102', 'J3':'MLX90614', 'J4':'DS1302',
 'J5':'ST7789 TFT', 'J6':'SD SPI', 'J7':'RGB CATHODE', 'J8':'BUZZER <=20mA',
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
mapping={ref:'/'+ids['root_uuid']+'/'+uid for ref,uid in ids.get('symbols',{}).items()}
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
for i,(x,y) in enumerate(((25,25),(155,25),(25,120),(155,120)),1):
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

text('NEOGUARD  |  MODULE CARRIER  |  REV A',90,25,1.5)
text('FUNCTIONAL CABLE HEADERS - VERIFY MODULE PIN ORDER',90,22.5,.9)
text('3.3V LOGIC ONLY   |   NO ONBOARD REGULATOR',90,121,1.0)
text('ONE SHUNT ONLY ON EACH 3-PIN SELECTOR',90,117.5,.9)
text('USB powers ESP32 separately - see assembly guide',90,123,.75)

# Compact labels with numbered pins are supplemented by the wiring table.
for c in M['components']:
 ref=c['ref']; x,y,r=POS[ref]
 if ref=='J1':
  text('J1 ESP32-S3 CABLE',34,42,1)
  text('NOT A DEVBOARD SOCKET',34,44,.8)
  left=['1 GND','3 SDA4','5 CLK6','7 CE14','9 DC9','11 MOSI11','13 BUZZ15','15 G17','17 CS21','19 MOSI41','21 GND','23 GND']
  right=['2 DEV3V3','4 SCL5','6 DAT7','8 RST8','10 CS10','12 SCK12','14 R16','16 B18','18 SCK40','20 MISO42','22 GND','24 GND']
  for i,(a,b) in enumerate(zip(left,right)):
   text(a,x-3,y+i*2.54,.75,p.GR_TEXT_H_ALIGN_RIGHT)
   text(b,x+5.5,y+i*2.54,.75,p.GR_TEXT_H_ALIGN_LEFT)
  fp=byref[ref]; fp.Reference().SetVisible(False)
 elif ref in ('J2','J3','J4'):
  text(SHORT_VALUES[ref],x-3,y-5,.95)
 elif ref in ('J5','J6'):
  text(SHORT_VALUES[ref],x-3,y-7 if ref=='J5' else y-12,.95)
 elif ref in ('J7','J8','J9'):
  text(SHORT_VALUES[ref],x-3,y+4,.85)
 elif ref=='JP1':
  text('DEV / 3V3 / EXT',x+4.5,y+2.54,.75,p.GR_TEXT_H_ALIGN_LEFT)
 elif ref=='JP2':
  text('3V3 / SD / 5V',x-4,y+2.54,.75,p.GR_TEXT_H_ALIGN_RIGHT)
 elif ref=='JP3':
  text('3V3 / BUZZ / 5V',x+4,y+2.54,.75,p.GR_TEXT_H_ALIGN_LEFT)
 elif ref=='JP4':
  text('BL: OPEN',x-4,y+1,.8,p.GR_TEXT_H_ALIGN_RIGHT)

# Signal names beside each module connector make harness mapping explicit.
for ref,labels in {
 'J2':['3V3','GND','SDA','SCL','NC'],
 'J3':['3V3','GND','SDA','SCL'],
 'J4':['3V3','GND','CLK','DAT','CE'],
 'J7':['R','G','B','GND'], 'J8':['+','-'], 'J9':['3V3','GND','5V']
}.items():
 for pad in byref[ref].Pads():
  xx,yy=xy(pad.GetPosition());text(labels[int(pad.GetNumber())-1],xx,yy-2.5,.8)
for ref,labels in {
 'J5':['GND','3V3','SCK12','MOSI11','RST8','DC9','CS10','BL'],
 'J6':['VCC','GND','SCK40','MOSI41','MISO42','CS21']
}.items():
 for pad in byref[ref].Pads():
  xx,yy=xy(pad.GetPosition());text(labels[int(pad.GetNumber())-1],xx-3,yy,.8,p.GR_TEXT_H_ALIGN_RIGHT)
text('1E 2B 3C',81.534,86.5,.8)

# Pad map and conservative route-clearance masks; bit-per-net allows same-net reuse.
bits={n:1<<i for i,n in enumerate(names)}
occupancy=[0]*(2*N)
print('Creating route mask',NX,NY,flush=True)
def box_cells(x,y,rx,ry):
 a,b=grid(x-rx,y-ry); c,d=grid(x+rx,y+ry)
 for j in range(max(0,b),min(NY-1,d)+1):
  for i in range(max(0,a),min(NX-1,c)+1): yield i,j
BLOCK=1<<len(names)
for z in (0,1):
 for j in range(NY):
  for i in range(NX):
   x,y=mm(i,j)
   if x<X0+1 or x>X1-1 or y<Y0+1 or y>Y1-1: occupancy[idx(i,j,z)]|=BLOCK
for x,y in holes:
 for i,j in box_cells(x,y,2.4,2.4):
  xx,yy=mm(i,j)
  if math.hypot(xx-x,yy-y)<=2.4:
   for z in(0,1): occupancy[idx(i,j,z)]|=BLOCK
for fp in board.GetFootprints():
 for pad in fp.Pads():
  x,y=xy(pad.GetPosition()); sx,sy=xy(pad.GetSize())
  bit=bits.get(pad.GetNetname().lstrip('/'),BLOCK)
  # Bounding rectangle conservatively covers oval/round pads and routing gap.
  for i,j in box_cells(x,y,sx/2+.58,sy/2+.58):
   for z in(0,1): occupancy[idx(i,j,z)]|=bit

def reserve_segment(a,b,bit,radius):
 x0,y0=mm(a[0],a[1]); x1,y1=mm(b[0],b[1]); z=a[2]
 for i,j in box_cells((x0+x1)/2,(y0+y1)/2,abs(x1-x0)/2+radius,abs(y1-y0)/2+radius):
  xx,yy=mm(i,j)
  dx=max(min(x0,x1)-xx,0,xx-max(x0,x1)); dy=max(min(y0,y1)-yy,0,yy-max(y0,y1))
  if dx*dx+dy*dy <= radius*radius: occupancy[idx(i,j,z)]|=bit

def via_free(i,j,bit):
 # Same-net copper may be reused, but drilled vias still need physical spacing.
 for vi,vj,vnet in vias_placed:
  if (vi!=i or vj!=j) and math.hypot(vi-i,vj-j)*STEP < 1.05:return False
 for z in (0,1):
  for dj in(-1,0,1):
   for di in(-1,0,1):
    if not(0<=i+di<NX and 0<=j+dj<NY): return False
    if occupancy[idx(i+di,j+dj,z)] & ~bit: return False
 return True

def route(net,start,target):
 bit=bits[net]; si,sj=grid(*xy(start.GetPosition())); ti,tj=grid(*xy(target.GetPosition()))
 def heuristic(i,j): return (abs(i-ti)+abs(j-tj))*10
 openq=[]; costs={}; came={}
 for z in(0,1):
  k=idx(si,sj,z); costs[k]=0; heapq.heappush(openq,(heuristic(si,sj),0,k))
 end=None; visited=0
 while openq:
  _,g,k=heapq.heappop(openq)
  if costs.get(k)!=g:continue
  i,j,z=unpack(k); visited+=1
  if i==ti and j==tj:end=k;break
  if visited>650000:return None
  for di,dj in((1,0),(-1,0),(0,1),(0,-1)):
   ni,nj=i+di,j+dj
   if not(0<=ni<NX and 0<=nj<NY):continue
   nk=idx(ni,nj,z)
   if occupancy[nk]&~bit:continue
   stepcost=10+(2 if ((z==0 and dj) or(z==1 and di)) else 0)
   ng=g+stepcost
   if ng<costs.get(nk,10**15):
    costs[nk]=ng;came[nk]=k;heapq.heappush(openq,(ng+heuristic(ni,nj),ng,nk))
  nk=idx(i,j,1-z);ng=g+100
  if ng<costs.get(nk,10**15) and via_free(i,j,bit):
   costs[nk]=ng;came[nk]=k;heapq.heappush(openq,(ng+heuristic(i,j),ng,nk))
 if end is None:return None
 path=[unpack(end)]
 while end in came:end=came[end];path.append(unpack(end))
 path.reverse();return path

def pcbtrack(xy1,xy2,layer,net,width):
 if xy1==xy2:return
 tr=p.PCB_TRACK(board);tr.SetStart(v(*xy1));tr.SetEnd(v(*xy2));tr.SetWidth(int(width*1e6));tr.SetLayer(p.F_Cu if layer==0 else p.B_Cu);tr.SetNet(nets[net]);board.Add(tr)

vias_placed=set()
def commit(path,net,a,b):
 bit=bits[net];width=.6 if net in POWER else .3
 # Merge straight runs, inserting vias only on layer changes.
 runs=[path[0]]
 for u in range(1,len(path)-1):
  prev,cur,nxt=path[u-1:u+2]
  d1=(cur[0]-prev[0],cur[1]-prev[1],cur[2]-prev[2]);d2=(nxt[0]-cur[0],nxt[1]-cur[1],nxt[2]-cur[2])
  if d1!=d2:runs.append(cur)
 runs.append(path[-1])
 pcbtrack(xy(a.GetPosition()),mm(*path[0][:2]),path[0][2],net,width)
 pcbtrack(mm(*path[-1][:2]),xy(b.GetPosition()),path[-1][2],net,width)
 for aa,bb in zip(runs,runs[1:]):
  if aa[2]==bb[2]:
   pcbtrack(mm(*aa[:2]),mm(*bb[:2]),aa[2],net,width)
   reserve_segment(aa,bb,bit,.92 if net in POWER else .77)
  else:
   key=(aa[0],aa[1],net)
   if key not in vias_placed:
    via=p.PCB_VIA(board);via.SetPosition(v(*mm(*aa[:2])));via.SetWidth(int(.8e6));via.SetDrill(int(.4e6));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNet(nets[net]);board.Add(via);vias_placed.add(key)
   for zz in(0,1):reserve_segment((aa[0],aa[1],zz),(aa[0],aa[1],zz),bit,1.02)

starttime=time.time();failed=[];routes=[]
# Reserve deterministic front-copper escape lanes before any global routing.
# This prevents late nets from becoming trapped inside the dense 2x12 harness.
for pad in byref['J1'].Pads():
 net=pad.GetNetname().lstrip('/')
 if not net: continue
 x,y=xy(pad.GetPosition()); destx=27.94 if int(pad.GetNumber())%2 else 45.974
 i,j=grid(x,y); di,dj=grid(destx,y)
 aa=(i,j,0);bb=(di,dj,0)
 reserve_segment(aa,bb,bits[net],.92 if net in POWER else .77)
# Short local signals first; broad rails last. Dense J1 signals before rails.
def spread(net):
 pts=[xy(pa.GetPosition()) for pa in pads[net]]
 return max(x for x,y in pts)-min(x for x,y in pts)+max(y for x,y in pts)-min(y for x,y in pts)
order=sorted(pads,key=lambda net:(net in POWER,spread(net)))
for net in order:
 todo=list(pads[net]); connected=[todo.pop(0)]
 while todo:
  a,b=min(((aa,bb) for aa in connected for bb in todo),key=lambda ab:math.dist(xy(ab[0].GetPosition()),xy(ab[1].GetPosition())))
  path=route(net,a,b)
  if path:
   commit(path,net,a,b);routes.append({'net':net,'a':a.GetParentFootprint().GetReference()+'.'+a.GetNumber(),'b':b.GetParentFootprint().GetReference()+'.'+b.GetNumber(),'steps':len(path)})
  else:
   failure=(net,a.GetParentFootprint().GetReference()+'.'+a.GetNumber(),b.GetParentFootprint().GetReference()+'.'+b.GetNumber());failed.append(failure);print('UNROUTED',failure,flush=True)
  connected.append(b);todo.remove(b)
 print('Routed',net,'of',len(pads),'elapsed',round(time.time()-starttime,1),flush=True)

board.GetTitleBlock().SetTitle('NeoGuard module carrier - functional cable headers')
board.GetTitleBlock().SetRevision('A');board.GetTitleBlock().SetDate('2026-10-20')
p.SaveBoard(str(ROOT/'NeoGuard.kicad_pcb'),board)
(ROOT/'routing_summary.json').write_text(json.dumps({'grid_mm':STEP,'signal_width_mm':.3,'power_width_mm':.6,'via_diameter_mm':.8,'via_drill_mm':.4,'board_size_mm':[X1-X0,Y1-Y0],'routed_connections':len(routes),'failed':failed,'routes':routes,'elapsed_seconds':time.time()-starttime},indent=2))
print('SAVED',len(routes),'connections;',len(failed),'unrouted',flush=True)
