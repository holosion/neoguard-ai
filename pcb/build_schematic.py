"""NeoGuard revision B: explicit ESP32 GPIO wiring and separate carrier power sheet."""
from pathlib import Path
import json, re, math, uuid, copy

ROOT=Path(__file__).resolve().parent
LIBROOT=Path(r'C:\Program Files\KiCad\10.0\share\kicad\symbols')
M=json.loads((ROOT/'design_manifest.json').read_text())
CM={c['ref']:c for c in M['components']}
NS=uuid.UUID('d620ef9a-1167-4b36-a1d1-cfb663e4d101')
def uid(s): return str(uuid.uuid5(NS,s))
def snap(v):return round(round(v/1.27)*1.27,4)
def sp(p):return (snap(p[0]),snap(p[1]))
RID=uid('schematic-root'); SID=uid('power-sheet-instance'); CID=uid('schematic-power')
class Atom(str): pass
def parse(src):
    toks=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',src);i=0
    def one():
        nonlocal i
        t=toks[i];i+=1
        if t=='(':
            o=[]
            while toks[i]!=')':o.append(one())
            i+=1;return o
        return json.loads(t) if t.startswith('"') else Atom(t)
    return one()
def dump(v):
    if isinstance(v,list):return '('+' '.join(dump(x) for x in v)+')'
    return str(v) if isinstance(v,Atom) else json.dumps(v,ensure_ascii=False)
def child(v,k):return next((x for x in v[1:] if isinstance(x,list) and x[0]==k),None)
def children(v,k):return [x for x in v[1:] if isinstance(x,list) and x[0]==k]
def rename(v,old,new):
    if isinstance(v,list):
        if len(v)>1 and v[0]=='symbol' and str(v[1]).startswith(old+'_'):v[1]=new+v[1][len(old):]
        for x in v:rename(x,old,new)
CACHE={}
def libsym(lib,name):
    if lib not in CACHE:
        t=parse((LIBROOT/(lib+'.kicad_sym')).read_text(encoding='utf-8'))
        CACHE[lib]={str(x[1]):x for x in children(t,'symbol')}
    s=copy.deepcopy(CACHE[lib][name]);e=child(s,'extends')
    if e:
        b=libsym(lib,str(e[1]));rename(b,str(b[1]),name);b[1]=name
        props={str(p[1]):p for p in children(b,'property')}
        props.update({str(p[1]):p for p in children(s,'property')})
        b=[x for x in b if not(isinstance(x,list) and x[0]=='property')];b.extend(props.values());s=b
    return s
def eff(size=1,justify='',hide=False,bold=False):
    return f'(effects (font (size {size} {size}) '+('bold' if bold else '')+') '+(f'(justify {justify}) ' if justify else '')+('hide' if hide else '')+')'
LIBS={}
for c in M['components']:
    lib,name=c['symbol'].split(':')
    if name not in LIBS:LIBS[name]=libsym(lib,name)

def custom_module(name,width,top,bottom,pins,side='right'):
    """Functional module interface, with actual carrier connector pad numbers."""
    body=f'(symbol "{name}_0_1" (rectangle (start {-snap(width/2)} {snap(top)}) (end {snap(width/2)} {snap(bottom)}) (stroke (width 0.254) (type default)) (fill (type background))))'
    ps=[]
    for n,pname,yy in pins:
        xx=(snap(width/2)+7.62) if side=='right' else (-snap(width/2)-7.62)
        ang=180 if side=='right' else 0
        hide='hide' if pname=='Pin_5' else ''
        ps.append(f'(pin passive line (at {xx} {yy} {ang}) (length 7.62) (name {json.dumps(pname)} (effects (font (size 1.05 1.05)) {hide})) (number "{n}" {eff(1.0)}))')
    s=f'(symbol "{name}" (pin_names (offset 1.27)) (in_bom yes) (on_board yes) (property "Reference" "J" (at 0 {top+3.81} 0) {eff(1.27)}) (property "Value" "{name}" (at 0 {bottom-3.81} 0) {eff(1.27)}) {body} (symbol "{name}_1_1" '+''.join(ps)+'))'
    LIBS[name]=parse(s)


# Fixed-direction symbol for the hardwired A->B buffer; no bidirectional outputs on A.
buffer=LIBS.pop('74HC245')
rename(buffer,'74HC245','SN74AHCT245_AtoB');buffer[1]='SN74AHCT245_AtoB'
for sub in children(buffer,'symbol'):
 for pin in children(sub,'pin'):
  number=int(child(pin,'number')[1])
  if 2 <= number <= 9: pin[1]=Atom('input')
  elif 11 <= number <= 18: pin[1]=Atom('output')
LIBS['SN74AHCT245_AtoB']=buffer
CM['U2']['symbol']='NeoGuard:SN74AHCT245_AtoB'
U1NET = {'4':'I2C_SDA_GPIO4','5':'I2C_SCL_GPIO5','6':'RTC_CLK_GPIO6','7':'RTC_DAT_GPIO7','14':'RTC_CE_GPIO14','8':'LCD_RS_GPIO8','9':'LCD_EN_GPIO9','10':'LCD_D4_GPIO10','11':'LCD_D5_GPIO11','12':'LCD_D6_GPIO12','13':'LCD_D7_GPIO13','15':'BUZZ_GPIO15','16':'LED_R_GPIO16','17':'LED_G_GPIO17','18':'LED_B_GPIO18','21':'SD_CS_GPIO21','40':'SD_SCK_GPIO40','41':'SD_MOSI_GPIO41','42':'SD_MISO_GPIO42','3V3':'DEV3V3','GND':'GND'}
custom_module('ESP32_S3_Logical',45,60,-60,[(n,net.replace('_GPIO',' / GPIO'),55.88-i*5.08) for i,(n,net) in enumerate(U1NET.items())])
def pin_defs(s):
    out=[]
    for sub in children(s,'symbol'):
        for p in children(sub,'pin'):
            at=child(p,'at');n=child(p,'number');out.append((str(n[1]),float(at[1]),float(at[2]),float(at[3])))
    return out
def pos(x,y,a,px,py):
    r=math.radians(a)
    return (round(x+px*math.cos(r)-py*math.sin(r),4),round(y-px*math.sin(r)-py*math.cos(r),4))

PLACED={};PATHS={};ALLPINS={}
class Page:
    def __init__(self,key,instpath):self.key=key;self.path=instpath;self.items=[];self.pins={}
    def add(self,s):self.items.append(s)
    def oid(self,kind):return uid(self.key+'-'+kind+'-'+str(len(self.items)))
    def text(self,s,x,y,size=1.1,bold=False):self.add(f'(text {json.dumps(s)} (at {x} {y} 0) {eff(size,"left top",bold=bold)} (uuid {self.oid("text")}))')
    def wire(self,a,b):
        a=sp(a);b=sp(b)
        if a!=b:self.add(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {self.oid("wire")}))')
    def pathwire(self,*pts):
        for a,b in zip(pts,pts[1:]):self.wire(a,b)
    def dot(self,p):
        p=sp(p);self.add(f'(junction (at {p[0]} {p[1]}) (diameter 0) (color 0 0 0 0) (uuid {self.oid("dot")}))')
    def label(self,net,p,angle=0):
        p=sp(p);self.add(f'(global_label {json.dumps(net)} (shape passive) (at {p[0]} {p[1]} {angle}) {eff(.95,"left")} (uuid {self.oid("glabel")}))')
    def place(self,ref,x,y,a=0,libname=None,showval=False,autolabel=False):
        x=snap(x);y=snap(y)
        c=CM[ref] if ref!='U1' else {'value':'ESP32-S3 DEVELOPMENT BOARD','footprint':'','pins':U1NET}
        name=libname or c['symbol'].split(':')[1];s=LIBS[name];sid=uid('instance-'+ref)
        PLACED[ref]=sid;PATHS[ref]=self.path+'/'+sid
        rx=x;ry=y-7;vx=x;vy=y-10
        if a in(90,270):rx=x-5;vx=x+5;ry=vy=y-3.5
        if ref=='U1':ry=y-65;vy=y-70
        props=f'(property "Reference" "{ref}" (at {rx} {ry} {a}) {eff(1.25)}) (property "Value" {json.dumps(c["value"])} (at {vx} {vy} {a}) {eff(1,"",not showval)}) (property "Footprint" {json.dumps(c["footprint"])} (at {x} {y} 0) {eff(1,"",True)})'
        ps=''
        for n,px,py,pa in pin_defs(s):
            pt=pos(x,y,a,px,py);self.pins[(ref,n)]=pt;ALLPINS[(ref,n)]=pt
            ps+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)}))'
            net=c['pins'][n]
            if net is None:self.add(f'(no_connect (at {pt[0]} {pt[1]}) (uuid {uid(ref+"-nc-"+n)}))')
            elif autolabel:
                rr=math.radians(a+pa)
                length=20.32 if ref=='J1' else 10.16
                q=(round(pt[0]-length*math.cos(rr),4),round(pt[1]+length*math.sin(rr),4))
                self.wire(pt,q);self.label(net,q,0 if math.cos(rr)<-.1 else 180)
        self.add(f'(symbol (lib_id "NeoGuard:{name}") (at {x} {y} {a}) (unit 1) (in_bom {"no" if ref=="U1" or ref.startswith("#") else "yes"}) (on_board {"no" if ref=="U1" or ref.startswith("#") else "yes"}) (dnp {"yes" if c.get("dnp") else "no"}) (uuid {sid}) {props} {ps} (instances (project "NeoGuard" (path "{self.path}" (reference "{ref}") (unit 1)))))')
    def p(self,ref,n):return self.pins[(ref,str(n))]
    def netstub(self,ref,n,delta=(5.08,0),angle=0):
        p=self.p(ref,n);q=(round(p[0]+delta[0],4),round(p[1]+delta[1],4));self.wire(p,q)
        c=CM[ref] if ref!='U1' else {'pins':U1NET};self.label(c['pins'][str(n)],q,angle)
    def save(self,filename,title,uuid_,page):
        defs=[]
        for name,s in LIBS.items():
            s=copy.deepcopy(s);s[1]='NeoGuard:'+name;defs.append(dump(s))
        head=f'(kicad_sch (version 20250114) (generator "neoguard_design") (uuid {uuid_}) (paper "A3") (title_block (title {json.dumps(title)}) (date "2026-10-22") (rev "LCD-C") (company "NeoGuard research prototype") (comment 1 "GPIO names are logical signals; verify actual module headers and voltages")) (lib_symbols '+''.join(defs)+')\n'
        tail=f'(sheet_instances (path "/" (page "{page}")))' if page==1 else ''
        (ROOT/filename).write_text(head+'\n'.join(self.items)+'\n'+tail+' (embedded_fonts no))\n',encoding='utf-8')


# Three readable sheets; global net labels preserve exact cross-sheet wiring.
main=Page('main','/'+RID)
main.text('AKENA NEOGUARD | LCD SYSTEM INTEGRATION',15,14,2.3,True)
main.text('Electrical pin map matches the 22 October LCD firmware. Module footprints and power ratings require physical confirmation.',15,23,1.15)
main.place('U1',65,140,libname='ESP32_S3_Logical',autolabel=True)
main.text('ESP32-S3 controller',30,65,1.5,True)
main.text('Logical GPIO numbers, not header positions.\nConnect through J1 on the carrier.\nExact devboard socket is not assumed.',20,215,1.15)
for ref,x,y,title in [('J2',185,65,'MAX30102 OXIMETER'),('J3',290,65,'MLX90614 INFRARED'),('J4',385,65,'DS1302 RTC'),('J6',185,130,'SD CARD MODULE'),('J7',290,130,'RGB COMMON CATHODE')]:
    main.text(title,x-35,y-24,1.3,True)
    main.place(ref,x,y,showval=False,autolabel=True)
main.text('Shared I2C: SDA GPIO4, SCL GPIO5.\nSensor headers are functional interfaces.\nReorder cable wires to match purchased modules.',135,91,1.05)
main.text('CR2032: trickle charging disabled in firmware.',330,90,1.0)
for ref,x,y in [('R3',260,175),('R4',305,175),('R5',350,175)]:main.place(ref,x,y,showval=True,autolabel=True)
main.text('Each LED colour has its own 330-ohm resistor.',240,198,1.1)
main.text('BUZZER DRIVER | GPIO15',150,208,1.4,True)
for ref,x,y in [('R6',165,237),('R7',210,237),('Q1',255,237),('D1',305,237),('J8',370,237)]:main.place(ref,x,y,showval=True,autolabel=True)
main.text('PN2222A E1 B2 C3; verify purchased transistor. D1 cathode -> buzzer positive. Driver sized for <=20mA.',145,263,1.0)
main.text('LCD pins GPIO8-13 -> sheet 2. SD stays GPIO21/40/41/42.',125,275,1.1)

LCDSID=uid('lcd-sheet-instance');LCDID=uid('lcd-sheet')
for sid,name,filename,y,page in [(LCDSID,'LCD on carrier','NeoGuard-lcd.kicad_sch',247,2),(SID,'Power and controller cable','NeoGuard-power.kicad_sch',266,3)]:
    main.add(f'(sheet (at 20 {y}) (size 90 12) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {sid}) (property "Sheetname" "{name}" (at 20 {y-1} 0) {eff(1.05,"left bottom")}) (property "Sheetfile" "{filename}" (at 20 {y+13} 0) {eff(1,"left top")}) (instances (project "NeoGuard" (path "/{RID}" (page "{page}")))))')

lcdpage=Page('lcd','/'+RID+'/'+LCDSID)
lcdpage.text('LCD1602 | PHYSICALLY MOUNTED ON THE CARRIER',15,14,2.3,True)
lcdpage.text('Assumed footprint: WC1602A, 80 x 36 mm, 16 pins at 2.54mm pitch. Verify against the actual display before manufacture.',15,23,1.15)
lcdpage.text('3.3V -> 5V UNIDIRECTIONAL BUFFER',35,45,1.5,True)
lcdpage.place('U2',105,108,showval=False,autolabel=True)
lcdpage.text('U2 MUST be SN74AHCT245N\nSymbol represents the hardwired A -> B direction.\nDo not substitute a 74HC245.\nDIR pin1 = 5V: A -> B.\nOE pin19 = GND: outputs enabled.\nUnused A6/A7 inputs grounded; B6/B7 left open.',25,166,1.15)
lcdpage.text('LCD 16 x 2 | 4-BIT MODE',270,45,1.5,True)
lcdpage.place('J5',310,108,showval=False,autolabel=True)
lcdpage.text('RS=GPIO8   EN=GPIO9\nD4=GPIO10  D5=GPIO11\nD6=GPIO12  D7=GPIO13\n\nRW grounded: ESP32 never reads a 5V bus.\nD0-D3 left unconnected.',263,166,1.15)
for ref,x,y in [('RV1',85,230),('R8',190,230),('C5',280,230),('C6',360,230)]:lcdpage.place(ref,x,y,showval=True,autolabel=True)
lcdpage.text('CONTRAST 10k',50,202,1.3,True)
lcdpage.text('BACKLIGHT 220R',155,202,1.3,True)
lcdpage.text('U2 BYPASS 100nF',250,202,1.3,True)
lcdpage.text('LCD BULK 10uF',330,202,1.3,True)
lcdpage.text('5V is supplied by regulated EXT5V, independent of ESP32 USB power. All grounds common. Power the controller and carrier together.',15,280,1.1)

power=Page('power','/'+RID+'/'+SID)
power.text('POWER SELECTION | CONTROLLER CABLE',15,14,2.3,True)
power.text('No regulator on this carrier. Connect regulated supplies only. Never short external power to a USB-powered ESP32 rail.',15,23,1.15)
for ref,x,y,title in [('J1',70,80,'ESP32-S3 FUNCTIONAL CABLE'),('J9',200,65,'REGULATED INPUT'),('JP1',325,65,'3V3 SOURCE'),('JP2',200,145,'SD SUPPLY'),('JP3',325,145,'BUZZER SUPPLY')]:
    power.text(title,x-35,y-23,1.35,True);power.place(ref,x,y,autolabel=True)
power.text('J1 is not a devboard socket.\nPin22 now carries LCD D7 / GPIO13.\nMap cable wires by GPIO name.\nUSB remains on the external controller.',20,135,1.15)
power.text('J9: 1=EXT3V3, 2=GND, 3=EXT5V\nEXT5V is required for LCD + U2.',160,91,1.1)
power.text('JP1: 1-2 DEV3V3; 2-3 EXT3V3\nOne shunt only. Do not bridge both.',285,91,1.1)
power.text('JP2: 1-2 = 3V3; 2-3 = 5V\nSelect to match the actual SD module.',160,171,1.1)
power.text('JP3: 1-2 = 3V3; 2-3 = 5V\nSelect to match the actual buzzer.',285,171,1.1)
for ref,x in [('C1',40),('C2',95),('C3',150),('C4',205),('R1',285),('R2',365)]:power.place(ref,x,235,showval=True,autolabel=True)
power.text('DECOUPLING: SENSOR 3V3 AND SD SUPPLY',20,207,1.3,True)
power.text('OPTIONAL I2C PULL-UPS',250,207,1.3,True)
power.text('R1/R2 DNP when breakout pull-ups already exist. SDA/SCL must be pulled up to 3.3V, never 5V.',200,265,1.05)

# Explicit power-origin flags for external regulated rails and the selected 3V3 rail.
LIBS['PWR_FLAG']=libsym('power','PWR_FLAG')
for i,net in enumerate(['GND','EXT5V','V3V3','LCD_LED_A']):
    ref='#FLG'+str(i+1)
    CM[ref]={'value':'PWR_FLAG','footprint':'','symbol':'power:PWR_FLAG','pins':{'1':net}}
    power.place(ref,45+i*45,275,libname='PWR_FLAG',autolabel=True)

main.save('NeoGuard.kicad_sch','Akena NeoGuard - LCD System',RID,1)
lcdpage.save('NeoGuard-lcd.kicad_sch','Akena NeoGuard - Mounted LCD and Logic Buffer',LCDID,2)
power.save('NeoGuard-power.kicad_sch','Akena NeoGuard - Power and Controller Cable',CID,3)
(ROOT/'NeoGuard.kicad_sym').write_text('(kicad_symbol_lib (version 20251024) (generator "neoguard_design")\n'+'\n'.join(dump(s) for s in LIBS.values())+'\n)\n',encoding='utf-8')
(ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "NeoGuard") (type "KiCad") (uri "${KIPRJMOD}/NeoGuard.kicad_sym") (options "") (descr "Akena LCD carrier symbols")))\n')
(ROOT/'schematic_ids.json').write_text(json.dumps({'root_uuid':RID,'paths':PATHS,'symbols':PLACED,'logical_controller':{'reference':'U1','on_board':False,'pin_nets':U1NET}},indent=2))
print('Wrote three-sheet LCD integration schematic.')
