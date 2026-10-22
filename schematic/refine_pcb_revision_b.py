"""Revision B routing and copper finish for the editable NeoGuard carrier.

Reads the existing PCB so physical footprint UUIDs and manually reviewed
connector positions are retained. Run with the Python bundled with KiCad.
The root schematic and per-reference instance paths remain authoritative.
"""
import heapq
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import pcbnew as p

ROOT = Path(__file__).resolve().parent
FILE = ROOT / 'NeoGuard.kicad_pcb'
STEP = .254
OX = OY = 20.066
NX, NY = 552, 414
N = NX * NY
POWER = {'V3V3', 'DEV3V3', 'EXT3V3', 'EXT5V', 'SD_VCC', 'BUZZ_VCC', 'BUZZ_SW'}

def v(x,y): return p.VECTOR2I(round(x*1e6),round(y*1e6))
def xy(point): return point.x/1e6,point.y/1e6
def grid(x,y): return round((x-OX)/STEP),round((y-OY)/STEP)
def mm(i,j): return OX+i*STEP,OY+j*STEP
def key(i,j,z): return z*N+j*NX+i
def unpack(k):
 z,k=divmod(k,N);j,i=divmod(k,NX);return i,j,z
def distseg(point,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1]
 if dx*dx+dy*dy<1e-12:return math.dist(point,a)
 t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
 return math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy)

def apply_paths(board):
 ids=json.loads((ROOT/'schematic_ids.json').read_text())
 full=ids.get('paths',ids.get('full_paths',{}))
 if not full:
  full={ref:'/'+ids['root_uuid']+'/'+uid for ref,uid in ids.get('symbols',{}).items()}
 for fp in board.GetFootprints():
  if fp.GetReference() in full:fp.SetPath(p.KIID_PATH(full[fp.GetReference()]))

def addtext(board,s,x,y,size=1.1):
 t=p.PCB_TEXT(board);t.SetText(s);t.SetPosition(v(x,y));t.SetLayer(p.F_SilkS)
 t.SetTextSize(v(size,size));t.SetTextThickness(round(.15e6));board.Add(t)

def finish_silk_and_outline(board):
 for drawing in list(board.GetDrawings()):
  if isinstance(drawing,p.PCB_TEXT):
   t=drawing.GetText()
   if 'NEOGUARD  |  MODULE CARRIER' in t:drawing.SetText('NEOGUARD  |  MODULE CARRIER  |  REV B')
   if t in ('GHOST RIDER','I2C / RTC','ALARM DRIVER','STATUS RGB','GROUND POURS: BOTH LAYERS'):
    board.Delete(drawing)
  elif isinstance(drawing,p.PCB_SHAPE) and drawing.GetLayer()==p.Edge_Cuts:board.Delete(drawing)
 points=[(22,20),(158,20),(160,22),(160,123),(158,125),(22,125),(20,123),(20,22)]
 for a,b in zip(points,points[1:]+points[:1]):
  d=p.PCB_SHAPE();d.SetShape(p.SHAPE_T_SEGMENT);d.SetLayer(p.Edge_Cuts)
  d.SetStart(v(*a));d.SetEnd(v(*b));d.SetWidth(round(.05e6));board.Add(d)
 addtext(board,'I2C / RTC',83,45.5,1.2)
 addtext(board,'ALARM DRIVER',67,71.5,1.1)
 addtext(board,'STATUS RGB',103,75.5,1.1)
 addtext(board,'GROUND POURS: BOTH LAYERS',104,65,1.05)

def build_routes(board):
 for item in list(board.GetTracks()):board.Delete(item)
 for zone in list(board.Zones()):board.Delete(zone)
 nets={net.GetNetname():net for net in board.GetNetInfo().NetsByNetcode().values() if net.GetNetname()}
 # Global labels across the revised sheets use names without a leading slash.
 for name,net in list(nets.items()):
  if name.startswith('/'):net.SetNetname(name[1:])
 nets={net.GetNetname():net for net in board.GetNetInfo().NetsByNetcode().values() if net.GetNetname()}
 pads=defaultdict(list)
 for fp in board.GetFootprints():
  for pad in fp.Pads():
   if pad.GetNetname() and not pad.GetNetname().startswith('unconnected-'):pads[pad.GetNetname()].append(pad)
 names=sorted(pads);bits={name:1<<i for i,name in enumerate(names)}
 BLOCK=1<<len(names);occ=[0]*(2*N);vias=set()
 def cells(x,y,rx,ry):
  a,b=grid(x-rx,y-ry);c,d=grid(x+rx,y+ry)
  for j in range(max(0,b),min(NY-1,d)+1):
   for i in range(max(0,a),min(NX-1,c)+1):yield i,j
 for z in(0,1):
  for j in range(NY):
   for i in range(NX):
    x,y=mm(i,j)
    if x<21.0 or x>159.0 or y<21.0 or y>124.0:occ[key(i,j,z)]|=BLOCK
 for fp in board.GetFootprints():
  for pad in fp.Pads():
   x,y=xy(pad.GetPosition());sx,sy=xy(pad.GetSize())
   bit=bits.get(pad.GetNetname(),BLOCK)
   for i,j in cells(x,y,sx/2+.58,sy/2+.58):
    for z in(0,1):occ[key(i,j,z)]|=bit
 for x,y in((25,25),(155,25),(25,120),(155,120)):
  for i,j in cells(x,y,2.5,2.5):
   if math.dist(mm(i,j),(x,y))<2.5:
    for z in(0,1):occ[key(i,j,z)]|=BLOCK
 def reserve(a,b,bit,r):
  aa=mm(*a[:2]);bb=mm(*b[:2]);z=a[2]
  for i,j in cells((aa[0]+bb[0])/2,(aa[1]+bb[1])/2,abs(bb[0]-aa[0])/2+r,abs(bb[1]-aa[1])/2+r):
   if distseg(mm(i,j),aa,bb)<=r:occ[key(i,j,z)]|=bit
 def viafree(i,j,bit):
  for vi,vj,nn in vias:
   if (vi!=i or vj!=j) and math.hypot(vi-i,vj-j)*STEP<1.05:return False
  for z in(0,1):
   for dj in(-1,0,1):
    for di in(-1,0,1):
     if not(0<=i+di<NX and 0<=j+dj<NY):return False
     if occ[key(i+di,j+dj,z)]&~bit:return False
  return True
 dirs=((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
 def route(net,a,b):
  bit=bits[net];si,sj=grid(*xy(a.GetPosition()));ti,tj=grid(*xy(b.GetPosition()))
  def h(i,j):
   dx,dy=abs(i-ti),abs(j-tj);return 14*min(dx,dy)+10*abs(dx-dy)
  q=[];costs={};came={};lastdir={}
  for z in(0,1):
   k=key(si,sj,z);costs[k]=0;heapq.heappush(q,(h(si,sj),0,k))
  end=None;visits=0
  while q:
   _,g,k=heapq.heappop(q)
   if costs.get(k)!=g:continue
   i,j,z=unpack(k);visits+=1
   if i==ti and j==tj:end=k;break
   if visits>800000:break
   for di,dj in dirs:
    ni,nj=i+di,j+dj
    if not(0<=ni<NX and 0<=nj<NY):continue
    nk=key(ni,nj,z)
    if occ[nk]&~bit:continue
    if di and dj and ((occ[key(ni,j,z)]|occ[key(i,nj,z)])&~bit):continue
    direction=(di,dj)
    # Straight 45-degree runs, few turns, and a preference for top routing.
    cost=(14 if di and dj else 10)+(2 if z else 0)
    if lastdir.get(k) not in(None,direction):cost+=12
    ng=g+cost
    if ng<costs.get(nk,10**12):
     costs[nk]=ng;came[nk]=k;lastdir[nk]=direction;heapq.heappush(q,(ng+h(ni,nj),ng,nk))
   nk=key(i,j,1-z);ng=g+180
   if ng<costs.get(nk,10**12) and viafree(i,j,bit):
    costs[nk]=ng;came[nk]=k;lastdir[nk]=None;heapq.heappush(q,(ng+h(i,j),ng,nk))
  if end is None:return None
  path=[unpack(end)]
  while end in came:end=came[end];path.append(unpack(end))
  return path[::-1]
 def segment(a,b,z,net,width):
  if math.dist(a,b)<.00001:return
  t=p.PCB_TRACK(board);t.SetStart(v(*a));t.SetEnd(v(*b));t.SetLayer(p.F_Cu if z==0 else p.B_Cu)
  t.SetWidth(round(width*1e6));t.SetNet(nets[net]);board.Add(t)
 def commit(path,net,a,b):
  bit=bits[net];width=.6 if net in POWER else .3
  runs=[path[0]]
  for n in range(1,len(path)-1):
   aa,bb,cc=path[n-1:n+2]
   d1=tuple(y-x for x,y in zip(aa,bb));d2=tuple(y-x for x,y in zip(bb,cc))
   if d1!=d2:runs.append(bb)
  runs.append(path[-1])
  segment(xy(a.GetPosition()),mm(*runs[0][:2]),runs[0][2],net,width)
  segment(mm(*runs[-1][:2]),xy(b.GetPosition()),runs[-1][2],net,width)
  for aa,bb in zip(runs,runs[1:]):
   if aa[2]==bb[2]:
    segment(mm(*aa[:2]),mm(*bb[:2]),aa[2],net,width)
    reserve(aa,bb,bit,.91 if net in POWER else .76)
   else:
    vk=(aa[0],aa[1],net)
    if vk not in vias:
     via=p.PCB_VIA(board);via.SetPosition(v(*mm(*aa[:2])));via.SetWidth(round(.8e6));via.SetDrill(round(.4e6))
     via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNet(nets[net]);board.Add(via);vias.add(vk)
    for z in(0,1):reserve((*aa[:2],z),(*aa[:2],z),bit,1.02)
 # Reserve unobstructed front-copper fanout lanes from the controller harness.
 for fp in board.GetFootprints():
  if fp.GetReference()=='J1':
   for pad in fp.Pads():
    net=pad.GetNetname()
    if net=='GND':continue
    x,y=xy(pad.GetPosition());ex=27.94 if int(pad.GetNumber())%2 else 45.974
    i,j=grid(x,y);ei,ej=grid(ex,y);reserve((i,j,0),(ei,ej,0),bits[net],.91 if net in POWER else .76)
 def span(net):
  pts=[xy(pa.GetPosition()) for pa in pads[net]]
  return max(x for x,y in pts)-min(x for x,y in pts)+max(y for x,y in pts)-min(y for x,y in pts)
 order=sorted((nn for nn in pads if nn!='GND'),key=lambda nn:(nn in POWER,span(nn)))
 stats=[];failed=[];started=time.time()
 for net in order:
  todo=list(pads[net]);connected=[todo.pop(0)]
  while todo:
   a,b=min(((aa,bb) for aa in connected for bb in todo),key=lambda ab:math.dist(xy(ab[0].GetPosition()),xy(ab[1].GetPosition())))
   path=route(net,a,b)
   if path:commit(path,net,a,b);stats.append(net)
   else:failed.append([net,a.GetParentFootprint().GetReference()+'.'+a.GetNumber(),b.GetParentFootprint().GetReference()+'.'+b.GetNumber()])
   connected.append(b);todo.remove(b)
  print('Rev B routed',net,'elapsed',round(time.time()-started,1),'failed',len(failed),flush=True)
 if failed:raise RuntimeError('Unrouted connections: '+json.dumps(failed))
 return {'routed_non_ground_connections':len(stats),'ground_strategy':'Filled F.Cu/B.Cu zones with stitching vias','failed':failed,'routing_seconds':time.time()-started}

def add_ground_finish(board):
 gnd=next((net for net in board.GetNetsByNetcode().values() if net.GetNetname()=='GND'),None)
 if not gnd:raise RuntimeError('GND net not found')
 tracks=list(board.GetTracks());footpads=[pa for fp in board.GetFootprints() for pa in fp.Pads()]
 allvias=[xy(t.GetPosition()) for t in tracks if isinstance(t,p.PCB_VIA)]
 def safe(x,y):
  if not(21.3<x<158.7 and 21.3<y<123.7):return False
  if any(math.dist((x,y),pp)<3.6 for pp in((25,25),(155,25),(25,120),(155,120))):return False
  if any(math.dist((x,y),pp)<1.05 for pp in allvias):return False
  for pa in footpads:
   xx,yy=xy(pa.GetPosition());sx,sy=xy(pa.GetSize())
   dx=max(abs(x-xx)-sx/2,0);dy=max(abs(y-yy)-sy/2,0)
   if math.hypot(dx,dy)<.72:return False
  for t in tracks:
   if isinstance(t,p.PCB_VIA):continue
   if distseg((x,y),xy(t.GetStart()),xy(t.GetEnd()))<t.GetWidth()/2e6+.72:return False
  return True
 points=[]
 # Stitch around the edge and near every module ground return.
 for xx in range(22,159,10):points.extend([(xx,22),(xx,123)])
 for yy in range(32,123,10):points.extend([(22,yy),(158,yy)])
 for pa in footpads:
  if pa.GetNetname()=='GND':
   xx,yy=xy(pa.GetPosition())
   for dx,dy in((2.54,0),(-2.54,0),(0,2.54),(0,-2.54),(2.54,2.54),(-2.54,-2.54)):
    if safe(xx+dx,yy+dy):points.append((xx+dx,yy+dy));break
 # Interior stitches keep the two returns tied together around signal channels.
 for xx in range(42,151,20):
  for yy in range(42,114,20):points.append((xx,yy))
 count=0
 for xx,yy in points:
  if not safe(xx,yy):continue
  via=p.PCB_VIA(board);via.SetPosition(v(xx,yy));via.SetWidth(round(.8e6));via.SetDrill(round(.4e6))
  via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNet(gnd);board.Add(via);allvias.append((xx,yy));count+=1
 polygon=[(22.4,20.75),(157.6,20.75),(159.25,22.4),(159.25,122.6),(157.6,124.25),(22.4,124.25),(20.75,122.6),(20.75,22.4)]
 for layer,name in((p.F_Cu,'GND TOP - THERMAL'),(p.B_Cu,'GND BOTTOM - THERMAL')):
  zone=p.ZONE(board);zone.SetLayer(layer);zone.SetNet(gnd);zone.SetZoneName(name)
  zone.SetLocalClearance(round(.25e6));zone.SetMinThickness(round(.2e6))
  zone.SetPadConnection(p.ZONE_CONNECTION_THERMAL);zone.SetThermalReliefGap(round(.3e6));zone.SetThermalReliefSpokeWidth(round(.4e6))
  zone.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS);zone.SetMinIslandArea(round(2e12))
  zone.SetHatchStyle(p.ZONE_BORDER_DISPLAY_STYLE_DIAGONAL_EDGE);zone.SetAssignedPriority(0)
  outline=zone.Outline();outline.NewOutline()
  for xx,yy in polygon:outline.Append(round(xx*1e6),round(yy*1e6))
  board.Add(zone)
 board.BuildConnectivity()
 filler=p.ZONE_FILLER(board)
 if not filler.Fill(board.Zones()):raise RuntimeError('KiCad zone fill did not complete')
 areas={zone.GetZoneName():zone.GetFilledPolysList(zone.GetLayer()).Area()/1e12 for zone in board.Zones()}
 return {'ground_stitching_vias_added':count,'filled_copper_area_mm2':areas,'island_removal':'always','zone_clearance_mm':.25,'thermal_gap_mm':.3,'thermal_spoke_mm':.4}

def run():
 board=p.LoadBoard(str(FILE));before={fp.GetReference():fp.m_Uuid.AsString() for fp in board.GetFootprints()}
 apply_paths(board);finish_silk_and_outline(board)
 stats=build_routes(board);stats.update(add_ground_finish(board))
 board.GetTitleBlock().SetRevision('B');board.GetTitleBlock().SetDate('2026-10-21')
 board.GetTitleBlock().SetTitle('NeoGuard module carrier - thermal ground pours and 45-degree routing')
 after={fp.GetReference():fp.m_Uuid.AsString() for fp in board.GetFootprints()}
 if before!=after:raise RuntimeError('Footprint UUIDs changed unexpectedly')
 p.SaveBoard(str(FILE),board)
 stats.update({'revision':'B','board_size_mm':[140,105],'copper_layers':2,'signal_width_mm':.3,'power_width_mm':.6,'via_diameter_mm':.8,'via_drill_mm':.4,'footprint_uuids_preserved':True})
 (ROOT/'routing_summary.json').write_text(json.dumps(stats,indent=2))
 print(json.dumps(stats,indent=2),flush=True)

if __name__=='__main__':run()
